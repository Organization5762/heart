import { filter, map, share } from "rxjs/operators";
import { stream } from "./websocket";

export const peripheralStream = stream.pipe(
  filter((msg) => msg.type === "peripheral"),
  map((msg) => msg),
  share()
);

export const frameStream = stream.pipe(
  filter((msg) => msg.type === "frame"),
  share()
);