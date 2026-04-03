import { render, screen } from "@testing-library/react";

import App from "./App";

test("renders wake and sleep controls", () => {
  render(<App />);
  expect(screen.getByText("Wake")).toBeInTheDocument();
  expect(screen.getByText("Sleep")).toBeInTheDocument();
});
