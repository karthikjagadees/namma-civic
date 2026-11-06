import React, { createContext, useContext, useMemo, useState } from 'react'

export type Lang = 'en' | 'kn'

type Dict = Record<string, { en: string; kn: string }>

const STRINGS: Dict = {
  brandKn: { en: 'ನಮ್ಮ ಸಿವಿಕ್ 2.0', kn: 'ನಮ್ಮ ಸಿವಿಕ್ 2.0' },
  brandEn: { en: 'Namma Civic 2.0', kn: 'ನಮ್ಮ ಸಿವಿಕ್ 2.0' },
  brandSub: { en: 'Bengaluru Civic Operations Platform', kn: 'ಬೆಂಗಳೂರು ನಾಗರಿಕ ಕಾರ್ಯಾಚರಣೆ ವೇದಿಕೆ' },
  home: { en: 'Home', kn: 'ಮುಖಪುಟ' },
  services: { en: 'Services', kn: 'ಸೇವೆಗಳು' },
  track: { en: 'Track Request', kn: 'ವಿನಂತಿ ಟ್ರ್ಯಾಕ್' },
  insights: { en: 'City Insights', kn: 'ನಗರದ ಸ್ಥಿತಿ' },
  departments: { en: 'Departments', kn: 'ಇಲಾಖೆಗಳು' },
  agents: { en: 'AI Agents', kn: 'ಏಐ ಏಜೆಂಟ್‌ಗಳು' },
  report: { en: 'Report an Issue', kn: 'ದೂರು ದಾಖಲಿಸಿ' },
  myRequests: { en: 'My Requests', kn: 'ನನ್ನ ವಿನಂತಿಗಳು' },
  signIn: { en: 'Sign in', kn: 'ಪ್ರವೇಶ' },
  heroTitle: { en: 'ಶುದ್ಧ ಬೆಂಗಳೂರು ಸುಗಮ ಜೀವನ', kn: 'ಶುದ್ಧ ಬೆಂಗಳೂರು ಸುಗಮ ಜೀವನ' },
  heroSub: {
    en: 'An AI-Powered Multi-Agent Civic Operations System for a Cleaner, Safer and Better Bengaluru',
    kn: 'ಸ್ವಚ್ಛ, ಸುರಕ್ಷಿತ ಮತ್ತು ಉತ್ತಮ ಬೆಂಗಳೂರಿಗಾಗಿ ಬಹು-ಏಜೆಂಟ್ ನಾಗರಿಕ ಕಾರ್ಯಾಚರಣೆ ವ್ಯವಸ್ಥೆ',
  },
  agentsTitle: { en: 'AI Multi-Agent System', kn: 'ಬಹು-ಏಜೆಂಟ್ ವ್ಯವಸ್ಥೆ' },
  agentsLede: { en: 'Autonomous agents to resolve civic issues', kn: 'ನಾಗರಿಕ ಸಮಸ್ಯೆಗಳನ್ನು ಬಗೆಹರಿಸುವ ಸ್ವಯಂಚಾಲಿತ ಏಜೆಂಟ್‌ಗಳು' },
  detect: { en: 'Detect', kn: 'ಪತ್ತೆ' },
  detectSub: { en: 'Analyze photos and identify the issue', kn: 'ಫೋಟೋ ನೋಡಿ ಸಮಸ್ಯೆಯನ್ನು ಗುರುತಿಸಿ' },
  merge: { en: 'Merge', kn: 'ವಿಲೀನ' },
  mergeSub: { en: 'Find and combine duplicate reports', kn: 'ನಕಲಿ ದೂರುಗಳನ್ನು ಒಂದು ಘಟನೆಗೆ ಸೇರಿಸಿ' },
  route: { en: 'Route', kn: 'ಮಾರ್ಗ' },
  routeSub: { en: 'Send to the right department', kn: 'ಸರಿಯಾದ ಇಲಾಖೆಗೆ ಕಳುಹಿಸಿ' },
  resolve: { en: 'Resolve', kn: 'ಪರಿಹಾರ' },
  resolveSub: { en: 'Track work and close the issue', kn: 'ಕೆಲಸವನ್ನು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ ಮುಚ್ಚಿ' },
  live: { en: 'Live Request Tracking', kn: 'ನೇರ ವಿನಂತಿ ಟ್ರ್ಯಾಕಿಂಗ್' },
  viewAll: { en: 'View all', kn: 'ಎಲ್ಲವನ್ನೂ ನೋಡಿ' },
  submitted: { en: 'Submitted', kn: 'ಸಲ್ಲಿಕೆ' },
  aiReview: { en: 'AI Review', kn: 'ಏಐ ಪರಿಶೀಲನೆ' },
  assigned: { en: 'Assigned', kn: 'ನಿಯೋಜನೆ' },
  inProgress: { en: 'In Progress', kn: 'ಪ್ರಗತಿಯಲ್ಲಿ' },
  resolved: { en: 'Resolved', kn: 'ಬಗೆಹರಿದಿದೆ' },
  recent: { en: 'Recent Requests', kn: 'ಇತ್ತೀಚಿನ ವಿನಂತಿಗಳು' },
  mapTitle: { en: 'Bengaluru Issue Map', kn: 'ಬೆಂಗಳೂರು ಸಮಸ್ಯೆ ನಕ್ಷೆ' },
  viewMap: { en: 'View Map', kn: 'ನಕ್ಷೆ ನೋಡಿ' },
  high: { en: 'High', kn: 'ಅಧಿಕ' },
  medium: { en: 'Medium', kn: 'ಮಧ್ಯಮ' },
  low: { en: 'Low', kn: 'ಕಡಿಮೆ' },
  glance: { en: 'City at a Glance', kn: 'ನಗರದ ಒಂದು ನೋಟ' },
  total: { en: 'Total Complaints', kn: 'ಒಟ್ಟು ದೂರುಗಳು' },
  inProgStat: { en: 'In Progress', kn: 'ಪ್ರಗತಿಯಲ್ಲಿ' },
  resolvedStat: { en: 'Resolved', kn: 'ಬಗೆಹರಿದಿದೆ' },
  avg: { en: 'Resolution rate', kn: 'ಪರಿಹಾರ ದರ' },
  sampleNote: {
    en: 'Example cards are illustrative. City figures come from the live service when it is running.',
    kn: 'ಉದಾಹರಣೆ ಕಾರ್ಡ್‌ಗಳು ಮಾದರಿ. ನಗರದ ಅಂಕಿಗಳು ಸೇವೆ ಚಾಲನೆಯಲ್ಲಿದ್ದಾಗ ನೇರವಾಗಿ ಬರುತ್ತವೆ.',
  },
  footer: {
    en: 'Namma Civic 2.0 · Bengaluru',
    kn: 'ನಮ್ಮ ಸಿವಿಕ್ 2.0 · ಬೆಂಗಳೂರು',
  },
}

interface LangCtx {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: keyof typeof STRINGS) => string
}

const Ctx = createContext<LangCtx | null>(null)

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>('en')
  const value = useMemo<LangCtx>(() => ({
    lang,
    setLang,
    t: (key) => STRINGS[key][lang],
  }), [lang])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLang() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useLang must be used inside LanguageProvider')
  return ctx
}
