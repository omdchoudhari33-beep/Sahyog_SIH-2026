import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders, signInAsStaff } from "../../../test-utils";
import InstitutionProjectsPage from "./page";
import { getInstitutionProjects, submitInstitutionDisposition } from "@/lib/api";

jest.mock("@/lib/api");

describe("InstitutionProjectsPage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    signInAsStaff("institution");
    jest.clearAllMocks();
  });

  it("shows a passed-pilot badge and removes the card once a disposition is recorded", async () => {
    getInstitutionProjects.mockResolvedValue([
      { ticket_id: 1, proposal_id: 9, verdict: "pass", created_at: "2026-01-01T00:00:00Z" },
    ]);
    submitInstitutionDisposition.mockResolvedValue({});

    renderWithProviders(<InstitutionProjectsPage />);

    expect(await screen.findByText("Pilot passed")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // stat card: 1 awaiting disposition

    await userEvent.click(screen.getByRole("button", { name: "Handed over to ULB/Panchayat" }));

    expect(submitInstitutionDisposition).toHaveBeenCalledWith(1, { proposalId: 9, disposition: "handover" });
    await waitFor(() => expect(screen.queryByText("Ticket #1")).not.toBeInTheDocument());
  });

  it("shows an inline error and keeps the card if recording the disposition fails", async () => {
    getInstitutionProjects.mockResolvedValue([
      { ticket_id: 2, proposal_id: 4, verdict: "pass", created_at: "2026-01-01T00:00:00Z" },
    ]);
    submitInstitutionDisposition.mockRejectedValue(new Error("network error"));

    renderWithProviders(<InstitutionProjectsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Startup / incubation spin-out" }));

    expect(await screen.findByText("Could not record the disposition. Please try again.")).toBeInTheDocument();
    expect(screen.getByText("Ticket #2")).toBeInTheDocument();
  });
});
