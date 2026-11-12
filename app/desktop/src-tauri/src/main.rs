#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{io::{BufRead, BufReader}, process::{Child, Command, Stdio}, sync::{Arc, Mutex, atomic::{AtomicBool, Ordering}}, time::Duration};
use serde::{Deserialize, Serialize};
use tauri::{Emitter, Manager, menu::{Menu, MenuItem}, tray::TrayIconBuilder};
use tauri_plugin_autostart::ManagerExt;

#[derive(Clone, Serialize, Deserialize)]
struct Connection { port: u16, token: String }
#[derive(Clone, Default)]
struct Backend {
    connection: Arc<Mutex<Option<Connection>>>,
    child: Arc<Mutex<Option<Child>>>,
    stopped: Arc<AtomicBool>,
}

#[tauri::command]
async fn connection(state: tauri::State<'_, Backend>) -> Result<Connection, String> {
    for _ in 0..100 {
        if let Some(value) = state.connection.lock().unwrap().clone() { return Ok(value); }
        tauri::async_runtime::spawn_blocking(|| std::thread::sleep(Duration::from_millis(100))).await.map_err(|_| "Falha ao aguardar backend")?;
    }
    Err("Não foi possível iniciar o backend. Verifique a instalação do Monitor.".into())
}

fn start_backend(app: tauri::AppHandle, backend: Backend) {
    std::thread::spawn(move || {
        let mut failures = 0;
        while !backend.stopped.load(Ordering::SeqCst) && failures < 5 {
            *backend.connection.lock().unwrap() = None;
            let mut command;
            if cfg!(debug_assertions) {
                let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
                command = Command::new(std::env::var("MONITOR_PYTHON").map(std::path::PathBuf::from).unwrap_or(root.join(".venv/Scripts/python.exe")));
                command.arg("-u").arg(root.join("app/backend/run_backend.py"));
            } else {
                let path = match std::env::current_exe() { Ok(path) => path.with_file_name("monitor-backend.exe"), Err(_) => break };
                command = Command::new(path);
            }
            #[cfg(windows)] {
                use std::os::windows::process::CommandExt;
                command.creation_flags(0x08000000);
            }
            command.env("MONITOR_PARENT_PIPE", "1").stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
            let mut child = match command.spawn() { Ok(child) => child, Err(_) => { failures += 1; std::thread::sleep(Duration::from_secs(2)); continue; } };
            let output = child.stdout.take();
            *backend.child.lock().unwrap() = Some(child);
            if let Some(output) = output {
                let mut line = String::new();
                if BufReader::new(output).read_line(&mut line).is_ok() {
                    if let Ok(value) = serde_json::from_str::<Connection>(&line) {
                        *backend.connection.lock().unwrap() = Some(value);
                        let _ = app.emit("backend-ready", ());
                    }
                }
            }
            loop {
                if backend.stopped.load(Ordering::SeqCst) { return; }
                let exited = backend.child.lock().unwrap().as_mut().map(|c| c.try_wait().ok().flatten().is_some()).unwrap_or(true);
                if exited { break; }
                std::thread::sleep(Duration::from_millis(500));
            }
            // Only lifecycle events are persisted, never credentials or the handshake.
            if let Ok(dir) = app.path().app_local_data_dir() {
                let _ = std::fs::create_dir_all(&dir);
                use std::io::Write;
                if let Ok(mut log) = std::fs::OpenOptions::new().create(true).append(true).open(dir.join("backend-lifecycle.log")) {
                    let _ = writeln!(log, "Backend encerrado inesperadamente; tentativa de reinício {}", failures + 1);
                }
            }
            failures += 1;
            std::thread::sleep(Duration::from_secs(2));
        }
        *backend.connection.lock().unwrap() = None;
    });
}

fn show(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") { let _ = window.show(); let _ = window.unminimize(); let _ = window.set_focus(); }
}

fn main() {
    let backend = Backend::default();
    let state = backend.clone();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| show(app)))
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, Some(vec!["--minimized"])))
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_opener::init())
        .manage(backend)
        .invoke_handler(tauri::generate_handler![connection])
        .setup(move |app| {
            let open = MenuItem::with_id(app, "open", "Abrir Monitor", true, None::<&str>)?;
            let new = MenuItem::with_id(app, "new", "Nova demanda", true, None::<&str>)?;
            let pause = MenuItem::with_id(app, "pause", "Verificações disponíveis nas próximas fases", false, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Sair", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &new, &pause, &quit])?;
            let icon = tauri::image::Image::new_owned(include_bytes!("../icons/tray.rgba").to_vec(), 32, 32);
            TrayIconBuilder::new().icon(icon).tooltip("Monitor").menu(&menu).on_menu_event(|app, event| match event.id.as_ref() {
                "open" => show(app),
                "new" => { show(app); let _ = app.emit("navigate", "new"); },
                "quit" => app.exit(0),
                _ => {},
            }).build(app)?;
            let marker = app.path().app_local_data_dir()?.join("autostart-configured");
            if !marker.exists() {
                if app.autolaunch().enable().is_ok() {
                    if let Some(parent) = marker.parent() { std::fs::create_dir_all(parent)?; }
                    std::fs::write(marker, "1")?;
                }
            }
            if std::env::args().any(|arg| arg == "--minimized") { if let Some(window) = app.get_webview_window("main") { window.hide()?; } }
            start_backend(app.handle().clone(), state);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event { let _ = window.hide(); api.prevent_close(); }
        })
        .build(tauri::generate_context!()).expect("Falha ao abrir Monitor");
    app.run(|app, event| {
        if let tauri::RunEvent::Exit = event {
            let backend = app.state::<Backend>();
            backend.stopped.store(true, Ordering::SeqCst);
            if let Some(mut child) = backend.child.lock().unwrap().take() {
                drop(child.stdin.take());
                for _ in 0..30 {
                    if child.try_wait().ok().flatten().is_some() { break; }
                    std::thread::sleep(Duration::from_millis(100));
                }
                if child.try_wait().ok().flatten().is_none() {
                    #[cfg(windows)] {
                        use std::os::windows::process::CommandExt;
                        let _ = Command::new("taskkill.exe").args(["/PID", &child.id().to_string(), "/T", "/F"]).creation_flags(0x08000000).output();
                    }
                    let _ = child.kill();
                }
                let _ = child.wait();
            };
        }
    });
}
