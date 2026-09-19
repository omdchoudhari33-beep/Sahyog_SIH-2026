import userEvent from "@testing-library/user-event";
import { screen, waitFor, within } from "@testing-library/react";
import { renderWithProviders, signInAsStaff } from "../../../test-utils";
import InstitutionMatchesPage from "./page";
import { decideInstitutionMatch, getInstitutionMatches } from "@/lib/api";

jest.mock("@/lib/api");

function makeMatches(n) {
  // No ticket_domain: the page falls back to rendering "Ticket #{id}" text
  // in that case (see app/institution/matches/page.js), which gives each
  // row a distinct, deterministic accessible name to query by below.
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    ticket_id: 100 + i,
    status: "proposed",
    similarity_score: 0.5,
    created_at: "2026-01-01T00:00:00Z",
  }));
}

describe("InstitutionMatchesPage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    signInAsStaff("institution");
    jest.clearAllMocks();
  });

  it("paginates the inbox client-side at 10 rows per page", async () => {
    getInstitutionMatches.mockResolvedValue(makeMatches(15));
    renderWithProviders(<InstitutionMatchesPage />);

    await waitFor(() => expect(screen.getAllByRole("row")).toHaveLength(11)); // 10 data rows + header
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(6); // remaining 5 + header
  });

  it("optimistically accepts a match and calls the backend", async () => {
    getInstitutionMatches.mockResolvedValue(makeMatches(1));
    decideInstitutionMatch.mockResolvedValue({ status: "accepted" });
    renderWithProviders(<InstitutionMatchesPage />);

    const row = await screen.findByRole("row", { name: /100/ });
    await userEvent.click(within(row).getByRole("button", { name: "Accept" }));

    expect(decideInstitutionMatch).toHaveBeenCalledWith(1, { decision: "accept" });
    await waitFor(() => expect(within(row).getByText("Accepted")).toBeInTheDocument());
  });

  it("reverts the optimistic update if the backend call fails", async () => {
    getInstitutionMatches.mockResolvedValue(makeMatches(1));
    decideInstitutionMatch.mockRejectedValue(new Error("network error"));
    renderWithProviders(<InstitutionMatchesPage />);

    const row = await screen.findByRole("row", { name: /100/ });
    await userEvent.click(within(row).getByRole("button", { name: "Decline" }));

    await waitFor(() => expect(within(row).getByText("Pending decision")).toBeInTheDocument());
  });
});
