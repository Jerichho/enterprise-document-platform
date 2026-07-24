import { describe, expect, it } from "vitest";

import { suggestedQuestionsForDocuments } from "./starterQuestions";

describe("suggestedQuestionsForDocuments", () => {
  it("hides suggestions when no documents exist", () => {
    expect(suggestedQuestionsForDocuments([])).toEqual([]);
  });

  it("derives PTO suggestions from indexed HR documents", () => {
    const questions = suggestedQuestionsForDocuments([
      { title: "PTO Policy", department: "HR", category: "Benefits" },
    ]);
    expect(questions.some((q) => /PTO/i.test(q))).toBe(true);
    expect(questions.some((q) => /phishing/i.test(q))).toBe(false);
    expect(questions.some((q) => /expense/i.test(q))).toBe(false);
  });

  it("includes phishing suggestions when IT security docs are indexed", () => {
    const questions = suggestedQuestionsForDocuments([
      { title: "Acceptable Use Policy", department: "IT", category: "Security" },
    ]);
    expect(questions.some((q) => /phishing/i.test(q))).toBe(true);
    expect(questions.some((q) => /PTO/i.test(q))).toBe(false);
  });
});
