import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { redactCredentials, userMessage } from "./scraper-agent";

describe("redactCredentials", () => {
  const originalEmail = process.env.BOOKUP_EMAIL;
  const originalPassword = process.env.BOOKUP_PASSWORD;

  beforeEach(() => {
    process.env.BOOKUP_EMAIL = "user@example.com";
    process.env.BOOKUP_PASSWORD = "SuperSecret123";
  });

  afterEach(() => {
    if (originalEmail === undefined) {
      delete process.env.BOOKUP_EMAIL;
    } else {
      process.env.BOOKUP_EMAIL = originalEmail;
    }
    if (originalPassword === undefined) {
      delete process.env.BOOKUP_PASSWORD;
    } else {
      process.env.BOOKUP_PASSWORD = originalPassword;
    }
  });

  test("replaces a literal password substring with [REDACTED]", () => {
    const text = '<input type="password" value="SuperSecret123">';
    const result = redactCredentials(text);
    expect(result).not.toContain("SuperSecret123");
    expect(result).toContain("[REDACTED]");
  });

  test("replaces a literal email substring with [REDACTED]", () => {
    const text = '<input id="email" value="user@example.com">';
    const result = redactCredentials(text);
    expect(result).not.toContain("user@example.com");
    expect(result).toContain("[REDACTED]");
  });

  test("is a no-op when env vars are unset", () => {
    delete process.env.BOOKUP_EMAIL;
    delete process.env.BOOKUP_PASSWORD;
    const text = "some arbitrary html with no credentials";
    expect(redactCredentials(text)).toBe(text);
  });

  test("is a no-op on empty string", () => {
    expect(redactCredentials("")).toBe("");
  });
});

describe("userMessage", () => {
  const originalEmail = process.env.BOOKUP_EMAIL;
  const originalPassword = process.env.BOOKUP_PASSWORD;

  beforeEach(() => {
    process.env.BOOKUP_EMAIL = "user@example.com";
    process.env.BOOKUP_PASSWORD = "SuperSecret123";
  });

  afterEach(() => {
    if (originalEmail === undefined) {
      delete process.env.BOOKUP_EMAIL;
    } else {
      process.env.BOOKUP_EMAIL = originalEmail;
    }
    if (originalPassword === undefined) {
      delete process.env.BOOKUP_PASSWORD;
    } else {
      process.env.BOOKUP_PASSWORD = originalPassword;
    }
  });

  test("does not leak raw credential values from snapshot.html", () => {
    const snapshot = {
      ok: true,
      title: "Logg inn",
      url: "https://www.bookup.no/login",
      html: '<input id="email" value="user@example.com"><input type="password" value="SuperSecret123">',
      interactive: [
        { tag: "input", text: "email input (placeholder=user@example.com)", selector: "#email" },
      ],
    };

    const message = userMessage(snapshot as any, 1, 5);

    expect(message).not.toContain("user@example.com");
    expect(message).not.toContain("SuperSecret123");
    expect(message).toContain("[REDACTED]");
  });

  test("does not leak raw credential values from snapshot.iframe_html", () => {
    const snapshot = {
      ok: true,
      title: "Logg inn",
      url: "https://www.bookup.no/login",
      html: "<html></html>",
      iframe_html: '<input type="password" value="SuperSecret123">',
    };

    const message = userMessage(snapshot as any, 1, 5);

    expect(message).not.toContain("SuperSecret123");
    expect(message).toContain("[REDACTED]");
  });
});
