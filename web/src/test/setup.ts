import "@testing-library/jest-dom/vitest";

Object.defineProperty(window.HTMLCanvasElement.prototype, "getContext", {
  configurable: true,
  value: () => ({
    canvas: document.createElement("canvas"),
    fillStyle: "#000000",
    fillRect: () => undefined,
    getImageData: () => ({ data: new Uint8ClampedArray([0, 0, 0, 255]) }),
  }),
});

afterEach(() => {
  vi.restoreAllMocks();
});
