import { ArrowRight, FileText, Folder } from "lucide-react";
import { useState } from "react";
import { files } from "../demo";
import type { Monitor } from "../store";
import { Callout, Empty, frontLabel, Panel, sample, soon } from "../ui";

export function Files({ m }: { m: Monitor }) {
  const [category, setCategory] = useState("Todas");
  const folder = m.storage?.files_dir;
  const list = files.filter(
    (f) =>
      (!m.front || f.front === m.front) &&
      (category === "Todas" || f.category === category) &&
      f.name.toLowerCase().includes(m.query.toLowerCase()),
  );
  return (
    <>
      <Panel
        title="Pasta do Monitor"
        action={
          <button
            className="ghost sm"
            onClick={() => m.setPage("Configurações")}
          >
            {folder ? "Alterar" : "Escolher pasta"}
            <ArrowRight size={16} />
          </button>
        }
      >
        <div className="panel-body">
          {folder ? (
            <>
              <p className="path">{folder}</p>
              <p>
                {m.storage?.last_backup
                  ? `Último backup do banco: ${new Date(m.storage.last_backup + "T12:00:00").toLocaleDateString("pt-BR")}.`
                  : "Nenhum backup gravado ainda."}{" "}
                {m.storage?.in_onedrive
                  ? "Pasta sincronizada pelo OneDrive."
                  : "Esta pasta não está no OneDrive."}
              </p>
            </>
          ) : (
            <p>
              Escolha a pasta onde o Monitor guarda backups, exportações e os
              arquivos que organizar. Uma pasta do OneDrive mantém tudo na
              nuvem.
            </p>
          )}
        </div>
      </Panel>
      <Panel title="Catálogo" action={m.preview ? sample : soon}>
        {m.preview ? (
          <>
            <div className="toolbar" style={{ padding: "0 20px 12px" }}>
              <p>Arquivos fictícios</p>
              <select
                aria-label="Categoria do arquivo"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {["Todas", "Proposta", "Briefing", "Material"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Arquivo</th>
                    <th>Frente</th>
                    <th>Categoria</th>
                    <th>Tamanho</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((f) => (
                    <tr key={f.name}>
                      <td>
                        <FileText size={16} aria-hidden />
                        {f.name}
                      </td>
                      <td>{frontLabel(f.front)}</td>
                      <td>{f.category}</td>
                      <td>{f.size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <Empty
            icon={Folder}
            text="A indexação da pasta, a busca e a classificação dos arquivos chegam em uma próxima versão."
          />
        )}
      </Panel>
    </>
  );
}
