import { describe, expect, it } from "vitest";
import { ApiError, api, parseErrorBody } from "@/lib/api";
import { mockFetch } from "./helpers";

describe("api client", () => {
  it("parses {error: string}, {error: {message, problems}} and FastAPI detail arrays", () => {
    expect(parseErrorBody({ error: "nope" }, 400)).toEqual({ message: "nope", problems: [] });
    expect(parseErrorBody({ error: { message: "Not ready to publish", problems: ["no video asset attached"] } }, 422)).toEqual({ message: "Not ready to publish", problems: ["no video asset attached"] });
    expect(parseErrorBody({ detail: [{ loc: ["body", "title"], msg: "Field required" }] }, 422).message).toBe("title: Field required");
  });

  it("throws ApiError with status and problems", async () => {
    mockFetch([["/request-publish", { error: { message: "Not ready to publish", problems: ["demo items cannot be published"] } }, 422]]);
    const err = await api.requestPublish(1).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.problems).toEqual(["demo items cannot be published"]);
  });
});
