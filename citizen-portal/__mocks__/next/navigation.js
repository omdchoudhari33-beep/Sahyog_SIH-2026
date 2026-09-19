// Manual mock for the app-router hooks these client pages use
// (useStaffGate's router.replace, Header's usePathname). Placed under
// __mocks__/next/ so Jest applies it automatically to every test - see
// https://jestjs.io/docs/manual-mocks#mocking-node-modules - no per-file
// jest.mock("next/navigation") call needed.
export const useRouter = () => ({
  push: jest.fn(),
  replace: jest.fn(),
  back: jest.fn(),
  prefetch: jest.fn(),
});

export const usePathname = () => "/";

export const useSearchParams = () => new URLSearchParams();

export const redirect = jest.fn();
