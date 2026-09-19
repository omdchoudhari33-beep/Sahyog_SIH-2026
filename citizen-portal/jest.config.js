const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

const customJestConfig = {
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  testEnvironment: "jest-environment-jsdom",
  // next/jest feeds jsconfig.json's "@/*" alias to its SWC transform (so
  // `import ... from "@/lib/api"` resolves fine inside page.js), but that
  // doesn't reach Jest's own resolver, which is what jest.mock("@/lib/api")
  // needs - confirmed by "Cannot find module '@/lib/api'" pointing at the
  // jest.mock() call, not the page's own import. Mapping it explicitly here
  // covers both.
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
};

module.exports = createJestConfig(customJestConfig);
