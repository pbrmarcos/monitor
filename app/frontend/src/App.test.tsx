import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, it, expect, vi } from "vitest";
import App from "./App";
import { DemandModal } from "./DemandModal";
afterEach(cleanup);
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
describe("Monitor interface", () => {
  it("navigates through all eight screens and filters demo demands", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByText("Explorar demonstração"));
    await user.click(screen.getByRole("button", { name: "Frente 02" }));
    expect(screen.getByText("Revisar briefing do projeto")).toBeInTheDocument();
    expect(
      screen.queryByText("Preparar proposta para Ana"),
    ).not.toBeInTheDocument();
    for (const name of [
      "Demandas",
      "E-mails",
      "Sites",
      "Redes sociais",
      "Arquivos",
      "Assistente",
      "Configurações",
    ]) {
      const buttons = screen.getAllByRole("button");
      const navButton = buttons.find(
        (b) => b.textContent?.replace(/\d+$/, "") === name,
      )!;
      await user.click(navButton);
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    }
  });
  it("requires follow-up date and submits explicit user input", async () => {
    const user = userEvent.setup(),
      save = vi.fn();
    render(
      <DemandModal
        value={{ stage: "acompanhar" }}
        saving={false}
        onClose={() => {}}
        onSave={save}
      />,
    );
    await user.type(screen.getByLabelText("Título"), "Retornar proposta");
    expect(screen.getByLabelText(/Data de retorno/)).toBeRequired();
    await user.click(screen.getByText("Salvar demanda"));
    expect(save).not.toHaveBeenCalled();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Etapa" }),
      "novo",
    );
    await user.click(screen.getByText("Salvar demanda"));
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Retornar proposta", stage: "novo" }),
    );
  });
});
