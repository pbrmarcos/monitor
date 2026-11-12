use std::{collections::HashSet, time::Duration};
use serde::Deserialize;
use tauri_plugin_notification::NotificationExt;
use super::{Backend, show};
use std::sync::atomic::Ordering;
use tauri::{Emitter, Manager};

#[derive(Deserialize)]
struct Notice { id: i32, title: String, body: String, demand_id: Option<i64> }

pub fn start(app: tauri::AppHandle, backend: Backend) {
    let callback_app = app.clone();
    let _ = app.notification().on_action(move |action| {
        let extra = action.notification().map(|n| n.extra());
        let notice_id = extra.and_then(|e| e.get("notice_id")).cloned();
        let demand_id = extra.and_then(|e| e.get("demand_id")).cloned();
        show(&callback_app);
        let _ = callback_app.emit("notification-open", serde_json::json!({"id": notice_id, "demand_id": demand_id}));
    });
    std::thread::spawn(move || {
        let client = match reqwest::blocking::Client::builder().no_proxy().timeout(Duration::from_secs(3)).build() {
            Ok(client) => client, Err(_) => return,
        };
        let mut sent = HashSet::new();
        let mut alert_state = false;
        while !backend.stopped.load(Ordering::SeqCst) {
            let connection = backend.connection.lock().unwrap().clone();
            if let Some(connection) = connection {
                let base = format!("http://127.0.0.1:{}", connection.port);
                if let Ok(response) = client.get(format!("{base}/agenda/alert")).bearer_auth(&connection.token).send() {
                    if let Ok(data) = response.json::<serde_json::Value>() {
                        let active = data["active"].as_bool().unwrap_or(false);
                        if active != alert_state {
                            if let Some(tray) = app.tray_by_id("monitor-tray") {
                                let mut pixels = include_bytes!("../icons/tray.rgba").to_vec();
                                if active {
                                    for y in 21_i32..32 { for x in 21_i32..32 {
                                        if (x-26).pow(2) + (y-26).pow(2) <= 25 {
                                            let offset = (y*32+x) as usize * 4;
                                            pixels[offset..offset+4].copy_from_slice(&[198,40,40,255]);
                                        }
                                    }}
                                }
                                let _ = tray.set_icon(Some(tauri::image::Image::new_owned(pixels,32,32)));
                                let _ = tray.set_tooltip(Some(if active { "Monitor — avisos pendentes" } else { "Monitor" }));
                            }
                            alert_state = active;
                        }
                    }
                }
                let feed = client.get(format!("{base}/notifications/desktop")).bearer_auth(&connection.token).send();
                if let Ok(response) = feed {
                    if let Ok(response) = response.error_for_status() {
                        if let Ok(items) = response.json::<Vec<Notice>>() {
                            for notice in items {
                                if !sent.contains(&notice.id) {
                                    let shown = app.notification().builder().id(notice.id)
                                        .title(notice.title).body(notice.body)
                                        .extra("notice_id", notice.id).extra("demand_id", notice.demand_id).show();
                                    if shown.is_err() { continue; }
                                    sent.insert(notice.id);
                                }
                                let _ = client.post(format!("{base}/notifications/{}/delivered", notice.id))
                                    .bearer_auth(&connection.token).send();
                            }
                        }
                    }
                }
            }
            for _ in 0..10 {
                if backend.stopped.load(Ordering::SeqCst) { return; }
                std::thread::sleep(Duration::from_millis(500));
            }
        }
    });
}
