import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { DraftBundle } from "../api";
import { DraftMessages } from "./DraftMessages";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
const items = [
  {
    label: "Leve e cordial",
    text: "Bom dia! Pode confirmar as especificações da proposta?",
  },
  {
    label: "Direto e objetivo",
    text: "Preciso da confirmação da proposta e da escolha sobre a devolução.",
  },
  {
    label: "Criar urgência",
    text: "A confirmação permite dar andamento ao pedido. Consegue retornar?",
  },
  {
    label: "Facilitar a resposta",
    text: "Proposta: OK ou Ajustar. Peça recebida: Fica ou Devolve.",
  },
];

it("shows four tone tabs and copies only the selected message", async () => {
  const user = userEvent.setup();
  const copy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
  render(<DraftMessages bundle={{ kind: "alternatives", items }} />);
  expect(screen.getAllByRole("tab")).toHaveLength(4);
  expect(screen.getByRole("tab", { name: "Leve e cordial" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await user.click(screen.getByRole("tab", { name: "Facilitar a resposta" }));
  expect(screen.getByRole("tabpanel")).toHaveTextContent(items[3].text);
  await user.click(
    screen.getByRole("button", { name: "Copiar Facilitar a resposta" }),
  );
  expect(copy).toHaveBeenCalledWith(items[3].text);
  expect(
    screen.getByRole("button", { name: "Copiar Facilitar a resposta" }),
  ).toHaveTextContent("Copiado");
});

it("shows every sequence message together and supports keyboard navigation for tones", async () => {
  const user = userEvent.setup();
  const sequence: DraftBundle = {
    kind: "sequence",
    items: items.map((item, index) => ({
      ...item,
      label: `Mensagem ${index + 1}`,
    })),
  };
  const { rerender } = render(<DraftMessages bundle={sequence} />);
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
  expect(
    screen.getAllByRole("button", { name: /Copiar Mensagem/ }),
  ).toHaveLength(4);
  expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  rerender(<DraftMessages bundle={{ kind: "alternatives", items }} />);
  await user.click(screen.getByRole("tab", { name: "Leve e cordial" }));
  await user.keyboard("{ArrowRight}");
  expect(
    screen.getByRole("tab", { name: "Direto e objetivo" }),
  ).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel")).toHaveTextContent(items[1].text);
});

it("reports a clipboard failure without pretending the message was copied", async () => {
  const user = userEvent.setup();
  vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(
    new Error("blocked"),
  );
  render(<DraftMessages bundle={{ kind: "alternatives", items }} />);
  await user.click(
    screen.getByRole("button", { name: "Copiar Leve e cordial" }),
  );
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Não foi possível copiar",
  );
  expect(screen.queryByText("Copiado")).not.toBeInTheDocument();
});
