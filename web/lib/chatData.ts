// Automatic answers for the chat box: taken from what the site itself says. No language model is involved,
// and the chat says so. Anything else a visitor writes is saved for the jouleWise team to answer.
import { SALES_EMAIL, SALES_PHONE } from "@/lib/contact";

export interface Topic { chip?: string; keys: string[]; a: string }

export const CHAT = {
  hello: "Ask a question about Regulatory Studio or leave a note for the jouleWise team. What you write here is saved so the team can read it and reply.",
  ask: "To hear back from a person, leave a name and a phone number or email below.",
  noted: "Thanks, the team has your message and will reply.",
  notedAsk: "Thanks, the team has your message. Leave a name and a phone number or email below so they can reply.",
  thanks: "Thank you. Someone from the jouleWise team will get back to you.",
  phone: SALES_PHONE,
  topics: [
    { chip: "What is Regulatory Studio?", keys: ["what is", "about", "who are", "regulatory studio", "joint venture"],
      a: "Regulatory Studio is a joint venture of jouleWise and Urja Praxis. Each week it summarises orders and draft regulations of CERC, APTEL and the state electricity commissions, traces each decision to the regulations it rests on, and has the summaries reviewed by the Urja Praxis legal team." },
    { chip: "Is this legal advice?", keys: ["legal advice", "advice", "rely", "liable", "awaiting", "review", "reviewed", "pending"],
      a: "No. Summaries are for information; read the original order before acting. Items marked \"awaiting legal review\" were prepared with AI and not yet checked by the legal team. For advice on your own case, ask for a project review." },
    { chip: "Which commissions do you cover?", keys: ["commission", "cover", "state", "aptel", "cerc", "which", "gerc", "uperc", "rerc", "tnerc", "merc", "kerc"],
      a: "CERC and APTEL, and state commissions including Gujarat, Rajasthan, Uttar Pradesh, Tamil Nadu, Karnataka and Maharashtra. Coverage depends on what each commission posts; the Archive page shows what was published week by week." },
    { chip: "Can you review my project?", keys: ["my project", "my plant", "review my", "applies to me", "captive", "open access", "consult", "help us", "assess"],
      a: "Yes. A plant or project impact review tells you whether a regulatory change applies to you, which assumptions to check, what data is needed and which options to evaluate. Use \"Discuss my project\" at the top of the page, or leave your details here." },
    { chip: "What does it cost?", keys: ["cost", "price", "fee", "charge", "pricing", "subscription", "pay"],
      a: "Reading the site and the weekly digest is free. Project reviews and advisory work are quoted for your case: leave your contact details here, or use \"Discuss my project\"." },
    { chip: "Talk to the team", keys: ["call", "phone", "email", "contact", "talk", "speak", "meeting", "demo"],
      a: `Write to ${SALES_EMAIL} or call ${SALES_PHONE}. You can also leave your details here and the team will get back to you.` },
    { keys: ["digest", "newsletter", "subscribe", "weekly", "email updates"],
      a: "The weekly digest comes out on Fridays. Subscribe on the Digest page to get it by email." },
  ] as Topic[],
};
