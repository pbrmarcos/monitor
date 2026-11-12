import { Plus } from "lucide-react";
import { stages } from "../api";
import { newDemand, type Monitor } from "../store";
import { dateLabel, frontLabel } from "../ui";

export function Demands({ m }: { m: Monitor }) {
  return (
    <div className="kanban">
      {Object.entries(stages).map(([stage, label]) => {
        const cards = m.visible.filter((d) => d.stage === stage);
        return (
          <section
            className="kanban-column"
            key={stage}
            aria-label={label}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const id = Number(e.dataTransfer.getData("text/plain"));
              const d = m.demands.find((item) => item.id === id);
              if (d && d.stage !== stage) m.moveDemand(d, stage);
            }}
          >
            <header>
              <h3>{label}</h3>
              <span className="count">{cards.length}</span>
            </header>
            {cards.map((d) => (
              <button
                className="kanban-card"
                key={d.id}
                draggable
                onDragStart={(e) =>
                  e.dataTransfer.setData("text/plain", String(d.id))
                }
                onClick={() => m.setDetail(d)}
              >
                <span className="eyebrow">{frontLabel(d.front_id)}</span>
                <strong>{d.title}</strong>
                <p>{d.next_action || "Defina a próxima ação"}</p>
                <footer>
                  <span>{dateLabel(d.due || d.return_date)}</span>
                  {d.priority === "alta" && (
                    <span className="tag priority">Alta</span>
                  )}
                </footer>
              </button>
            ))}
            <button
              className="ghost"
              onClick={() =>
                m.setEditing({
                  ...newDemand(),
                  stage,
                  front_id: m.front || 1,
                })
              }
            >
              <Plus size={16} />
              Adicionar
            </button>
          </section>
        );
      })}
    </div>
  );
}
