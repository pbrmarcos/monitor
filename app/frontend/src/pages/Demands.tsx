import { Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { stages, type Demand } from "../api";
import { newDemand, type Monitor } from "../store";
import { dateLabel, frontLabel } from "../ui";

type Drag = {
  demand: Demand;
  x: number;
  y: number;
  offsetX: number;
  offsetY: number;
  width: number;
};
const THRESHOLD = 6;

export function Demands({ m }: { m: Monitor }) {
  const [drag, setDrag] = useState<Drag | null>(null);
  const [target, setTarget] = useState<string | null>(null);
  // Um clique não deve abrir o cartão que acabou de ser solto.
  const dragged = useRef(false);
  const stop = useRef<(() => void) | null>(null);
  useEffect(() => () => stop.current?.(), []);

  const stageAt = (x: number, y: number) =>
    document
      .elementsFromPoint(x, y)
      .map((el) => el.closest<HTMLElement>("[data-stage]"))
      .find(Boolean)?.dataset.stage ?? null;

  // Eventos de ponteiro em vez do arrastar nativo do HTML, que a janela do
  // aplicativo no Windows intercepta.
  function press(e: ReactPointerEvent<HTMLButtonElement>, demand: Demand) {
    if (e.button !== 0) return;
    const box = e.currentTarget.getBoundingClientRect();
    const start = { x: e.clientX, y: e.clientY };
    let active = false;
    dragged.current = false;
    const move = (ev: PointerEvent) => {
      if (
        !active &&
        Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < THRESHOLD
      )
        return;
      active = dragged.current = true;
      ev.preventDefault();
      setDrag({
        demand,
        x: ev.clientX,
        y: ev.clientY,
        offsetX: start.x - box.left,
        offsetY: start.y - box.top,
        width: box.width,
      });
      setTarget(stageAt(ev.clientX, ev.clientY));
    };
    const end = (ev: PointerEvent) => {
      stop.current?.();
      if (!active || ev.type !== "pointerup") return;
      const stage = stageAt(ev.clientX, ev.clientY);
      if (stage && stage !== demand.stage) m.moveDemand(demand, stage);
    };
    const cancel = (ev: KeyboardEvent) => ev.key === "Escape" && stop.current?.();
    stop.current = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
      window.removeEventListener("keydown", cancel);
      stop.current = null;
      setDrag(null);
      setTarget(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
    window.addEventListener("keydown", cancel);
  }

  const card = (d: Demand) => (
    <>
      <span className="eyebrow">{frontLabel(d.front_id)}</span>
      <strong>{d.title}</strong>
      <p>{d.next_action || "Defina a próxima ação"}</p>
      <footer>
        <span>{dateLabel(d.due || d.return_date)}</span>
        {d.priority === "alta" && <span className="tag priority">Alta</span>}
      </footer>
    </>
  );

  return (
    <div className={`kanban ${drag ? "dragging" : ""}`}>
      {Object.entries(stages).map(([stage, label]) => {
        const cards = m.visible.filter((d) => d.stage === stage);
        const receiving = drag && target === stage && drag.demand.stage !== stage;
        return (
          <section
            className={`kanban-column ${receiving ? "target" : ""}`}
            key={stage}
            aria-label={label}
            data-stage={stage}
          >
            <header>
              <h3>{label}</h3>
              <span className="count">{cards.length}</span>
            </header>
            {cards.map((d) => (
              <button
                className={`kanban-card ${drag?.demand.id === d.id ? "lifted" : ""}`}
                key={d.id}
                onPointerDown={(e) => press(e, d)}
                onClick={() => {
                  if (dragged.current) dragged.current = false;
                  else m.setDetail(d);
                }}
              >
                {card(d)}
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
      {drag && (
        <div
          className="kanban-card kanban-ghost"
          aria-hidden
          style={{
            left: drag.x - drag.offsetX,
            top: drag.y - drag.offsetY,
            width: drag.width,
          }}
        >
          {card(drag.demand)}
        </div>
      )}
    </div>
  );
}
