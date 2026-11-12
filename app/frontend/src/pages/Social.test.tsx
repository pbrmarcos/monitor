import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { useState } from "react";
import { Social } from "./Social";
import * as client from "../api";
import type { Monitor } from "../store";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("connects a Prospect profile without a Meta token, pauses it and reviews comments", async () => {
  const user = userEvent.setup();
  let profiles: client.SocialProfile[] = [];
  let records = [
    {
      id: 1,
      front_id: 2,
      profile_id: 1,
      author: "cliente",
      text: "Qual o valor?",
      reason: "Pedido comercial",
      post_url: "https://www.instagram.com/p/ABC/",
      published_at: new Date().toISOString(),
      status: "revisar",
      demand_id: null as number | null,
    },
  ];
  const calls = vi
    .spyOn(client, "api")
    .mockImplementation(async (path, method, body) => {
      if (path === "/social/browser/profiles")
        return [
          {
            account_id: 1,
            name: "Nextlink",
            username: "next.link",
            path: "C:/fixtures/conta-1",
          },
        ] as never;
      if (path === "/social/comments") return records as never;
      if (path === "/social") return profiles as never;
      if (path === "/social/browser" && method === "POST") {
        profiles = [
          {
            id: 1,
            front_id: 2,
            username: "next.link",
            name: "Nextlink",
            network: "instagram",
            avatar: "",
            method: "browser",
            enabled: true,
            auto_demands: true,
            status: "aguardando",
            status_detail: "",
            last_sync: null,
            followers: null,
            posts: null,
            followers_change: null,
            change_days: 0,
            posts_week: null,
            stories_week: null,
            likes_week: null,
            comments_week: null,
          },
        ];
        return profiles[0] as never;
      }
      if (path === "/social/1/browser") {
        profiles = [{ ...profiles[0], ...(body as object) }];
        return profiles[0] as never;
      }
      if (path === "/social/comments/1/accept") {
        records = [{ ...records[0], status: "demanda", demand_id: 7 }];
        return { demand_id: 7 } as never;
      }
      throw new Error(`Unexpected request ${path}`);
    });
  function Harness() {
    const [social, setSocial] = useState<client.SocialProfile[]>([]);
    const monitor = {
      social,
      setSocial,
      connected: true,
      preview: false,
      front: 0,
      demands: [],
      refreshDemands: async () => {},
      fail: vi.fn(),
      setNotice: vi.fn(),
      setDetail: vi.fn(),
      setPage: vi.fn(),
    } as unknown as Monitor;
    return <Social m={monitor} />;
  }
  render(<Harness />);
  await waitFor(() =>
    expect(screen.getByLabelText("Conta do Instagram Prospect")).toHaveValue(
      "1",
    ),
  );
  expect(
    screen.getAllByLabelText("Frente", { selector: "select" })[0],
  ).toHaveValue("2");
  await user.click(
    screen.getByRole("button", { name: "Conectar perfil do Chrome" }),
  );
  expect(calls).toHaveBeenCalledWith("/social/browser", "POST", {
    account_id: 1,
    front_id: 2,
    auto_demands: true,
  });
  await user.click(
    await screen.findByRole("button", { name: "Pausar coleta" }),
  );
  expect(
    await screen.findByRole("button", { name: "Retomar coleta" }),
  ).toBeEnabled();
  await user.click(screen.getByRole("button", { name: "Criar demanda" }));
  expect(
    await screen.findByRole("button", { name: "Abrir demanda #7" }),
  ).toBeInTheDocument();
});
