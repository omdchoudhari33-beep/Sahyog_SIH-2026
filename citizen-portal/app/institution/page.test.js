import { screen, waitFor, within } from "@testing-library/react";
import { renderWithProviders, signInAsStaff } from "../../test-utils";
import InstitutionDashboardPage from "./page";
import { getInstitutionMatches, getInstitutionPartners, getInstitutionProjects } from "@/lib/api";

jest.mock("@/lib/api");

// StatCard (components/StatCard.js) renders {value, label} as sibling divs
// inside one ".gov-card" - scoping by the label's own card is what lets these
// assertions tell "1 pending match" apart from "1 accepted match" instead of
// both matching a bare getByText("1").
function statValue(label) {
  return within(screen.getByText(label).closest(".gov-card")).getByText((content, el) => el.tagName === "DIV" && el.className.includes("font-serif"));
}

describe("InstitutionDashboardPage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    signInAsStaff("institution");
    jest.clearAllMocks();
  });

  it("aggregates match/project/partner data into the summary stat cards", async () => {
    getInstitutionMatches.mockResolvedValue([
      { id: 1, status: "proposed", ticket_id: 10 },
      { id: 2, status: "accepted", ticket_id: 11 },
      { id: 3, status: "declined", ticket_id: 12 },
    ]);
    getInstitutionProjects.mockResolvedValue([{ ticket_id: 20, proposal_id: 5, created_at: "2026-01-01" }]);
    getInstitutionPartners.mockResolvedValue([
      { id: 1, proposal_id: 5, total_committed_amount: 50000 },
      { id: 2, proposal_id: 6, total_committed_amount: 25000 },
    ]);

    renderWithProviders(<InstitutionDashboardPage />);

    await waitFor(() => expect(statValue("Pending matches")).toHaveTextContent("1"));
    expect(statValue("Accepted matches")).toHaveTextContent("1");
    expect(statValue("Declined matches")).toHaveTextContent("1");
    expect(statValue("Awaiting disposition")).toHaveTextContent("1");
    expect(statValue("Industry partners")).toHaveTextContent("2");

    // Total committed funding is summed across both ledgers.
    await waitFor(() => expect(screen.getByText("₹75,000")).toBeInTheDocument());
  });

  it("shows a retry-able error state for a section whose backend call fails", async () => {
    getInstitutionMatches.mockRejectedValue(new Error("network error"));
    getInstitutionProjects.mockResolvedValue([]);
    getInstitutionPartners.mockResolvedValue([]);

    renderWithProviders(<InstitutionDashboardPage />);

    expect(await screen.findByText(/could not reach the server/i)).toBeInTheDocument();
  });
});
