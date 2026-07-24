/** Suggested starter questions derived from indexed documents (no LLM call). */

export type SuggestionDocument = {
  title: string;
  department: string;
  category: string;
};

type CuratedRule = {
  match: RegExp;
  questions: string[];
};

const CURATED: CuratedRule[] = [
  {
    match: /\b(pto|paid time off|leave|vacation)\b/i,
    questions: [
      "How many PTO days do employees receive?",
      "Can unused PTO be carried over?",
      "Who is eligible for PTO?",
      "When does PTO eligibility begin?",
    ],
  },
  {
    match: /\b(phishing|cyber|security|acceptable use|malware)\b/i,
    questions: [
      "How should employees report a phishing attempt?",
      "Where should suspected malware be reported?",
      "Are personal cloud drives allowed for company data?",
    ],
  },
  {
    match: /\b(expense|reimbursement|travel|meal)\b/i,
    questions: [
      "What is the daily meal expense limit for domestic travel?",
      "How do employees submit expense reports?",
    ],
  },
  {
    match: /\b(forklift|safety|warehouse)\b/i,
    questions: [
      "What safety equipment is required for forklift operators?",
      "What are the warehouse safety rules?",
    ],
  },
];

/**
 * Build suggested questions from completed documents.
 * Returns an empty list when nothing is indexed.
 */
export function suggestedQuestionsForDocuments(
  documents: SuggestionDocument[],
  limit = 6,
): string[] {
  if (!documents.length) {
    return [];
  }

  const selected: string[] = [];
  const seen = new Set<string>();

  for (const doc of documents) {
    const haystack = `${doc.title} ${doc.department} ${doc.category}`;
    for (const rule of CURATED) {
      if (!rule.match.test(haystack)) continue;
      for (const question of rule.questions) {
        if (seen.has(question)) continue;
        seen.add(question);
        selected.push(question);
        if (selected.length >= limit) {
          return selected;
        }
      }
    }
  }

  // Fallback: title-based prompts when no curated rule matched.
  if (!selected.length) {
    for (const doc of documents.slice(0, limit)) {
      const question = `What are the key points in ${doc.title}?`;
      if (!seen.has(question)) {
        seen.add(question);
        selected.push(question);
      }
    }
  }

  return selected;
}
