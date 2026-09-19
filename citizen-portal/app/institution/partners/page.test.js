import userEvent from "@testing-library/user-event";
import { screen, waitFor, within } from "@testing-library/react";
import { renderWithProviders, signInAsStaff } from "../../../test-utils";
import InstitutionPartnersPage from "./page";
import { getInstitutionPartners, releasePartnerFunds } from "@/lib/api";

jest.mock("@/lib/api");

describe("InstitutionPartnersPage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    signInAsStaff("institution");
    jest.clearAllMocks();
  });

  it("labels the status column correctly and shows real ledger status, not IP tier", async () => {
    // Regression test: this column used to be headed "IP ownership tier" but
    // rendered `l.status` underneath it - LedgerOut (7.Industry Partnership/
    // app/schemas.py) has no tier field at all, so the header was always
    // describing the wrong data.
    getInstitutionPartners.mockResolvedValue([
      { id: 1, proposal_id: 9, status: "committed", total_committed_amount: 50000, currency: "INR" },
      { id: 2, proposal_id: 10, status: "fully_released", total_committed_amount: 25000, currency: "INR" },
    ]);

    renderWithProviders(<InstitutionPartnersPage />);

    expect(await screen.findByRole("columnheader", { name: "Status" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "IP ownership tier" })).not.toBeInTheDocument();
    const tbody = document.querySelector("tbody");
    expect(within(tbody).getByText("Committed")).toBeInTheDocument();
    expect(within(tbody).getByText("Fully released")).toBeInTheDocument();

    // Release button only offered for ledgers not yet fully released.
    expect(screen.getAllByRole("button", { name: "Release funds" })).toHaveLength(1);

    // Stat card: total committed funding summed across both ledgers.
    await waitFor(() => expect(screen.getByText("₹75,000")).toBeInTheDocument());
  });

  it("releases funds and updates that ledger's status in place", async () => {
    getInstitutionPartners.mockResolvedValue([
      { id: 1, proposal_id: 9, status: "committed", total_committed_amount: 50000, currency: "INR" },
    ]);
    releasePartnerFunds.mockResolvedValue({ status: "fully_released" });

    renderWithProviders(<InstitutionPartnersPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Release funds" }));

    expect(releasePartnerFunds).toHaveBeenCalledWith(1, { amount: 50000, releasedBy: "institution-portal" });
    await waitFor(() => expect(within(document.querySelector("tbody")).getByText("Fully released")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Release funds" })).not.toBeInTheDocument();
  });
});
