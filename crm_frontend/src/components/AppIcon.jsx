const ICONS = {
  leads: (
  <>
    <circle cx="18" cy="14" r="5" fill="currentColor" opacity="0.9" />
    <path d="M8 32c0-6 4.5-10 10-10s10 4 10 10" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" />
    <path d="M30 12l4-2 2 4-6 4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </>
  ),
  pipeline: (
  <>
    <rect x="8" y="22" width="8" height="12" rx="2" fill="currentColor" opacity="0.55" />
    <rect x="18" y="16" width="8" height="18" rx="2" fill="currentColor" opacity="0.75" />
    <rect x="28" y="10" width="8" height="24" rx="2" fill="currentColor" />
  </>
  ),
  followups: (
  <>
    <path d="M10 14h18a3 3 0 013 3v8a3 3 0 01-3 3H18l-6 5v-5h-2a3 3 0 01-3-3v-8a3 3 0 013-3z" fill="currentColor" opacity="0.85" />
    <circle cx="17" cy="21" r="1.5" fill="#fff" />
    <circle cx="22" cy="21" r="1.5" fill="#fff" />
    <circle cx="27" cy="21" r="1.5" fill="#fff" />
  </>
  ),
  contacts: (
  <>
    <circle cx="16" cy="15" r="5" fill="currentColor" />
    <circle cx="28" cy="17" r="4" fill="currentColor" opacity="0.65" />
    <path d="M8 32c0-5 3.5-8 8-8M22 32c0-4 2.5-6.5 6-6.5" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" />
  </>
  ),
  notes: (
  <>
    <rect x="10" y="8" width="24" height="28" rx="3" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="2" />
    <path d="M15 16h14M15 22h10M15 28h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  quotations: (
  <>
    <path d="M12 8h18l4 6v20H12z" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <path d="M18 20h12M18 26h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <text x="16" y="18" fontSize="8" fill="currentColor" fontWeight="700">₹</text>
  </>
  ),
  invoices: (
  <>
    <rect x="10" y="10" width="24" height="26" rx="3" fill="currentColor" opacity="0.9" />
    <path d="M15 18h14M15 24h10M15 30h12" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  payments: (
  <>
    <rect x="8" y="14" width="28" height="18" rx="4" fill="currentColor" />
    <rect x="8" y="20" width="28" height="6" fill="currentColor" opacity="0.35" />
    <circle cx="14" cy="27" r="2" fill="#fff" />
  </>
  ),
  tax: (
  <>
    <circle cx="22" cy="22" r="12" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="2" />
    <text x="22" y="27" textAnchor="middle" fontSize="11" fill="currentColor" fontWeight="800">GST</text>
  </>
  ),
  ledger: (
  <>
    <path d="M10 10h24v26H10z" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="2" />
    <path d="M15 18h14M15 24h14M15 30h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  orders: (
  <>
    <path d="M12 12h8l2 4h10v16H10V12z" fill="currentColor" opacity="0.85" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    <circle cx="18" cy="34" r="2" fill="currentColor" />
    <circle cx="30" cy="34" r="2" fill="currentColor" />
  </>
  ),
  projects: (
  <>
    <rect x="10" y="12" width="24" height="22" rx="3" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="2" />
    <path d="M16 20l4 4 8-8" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </>
  ),
  products: (
  <>
    <path d="M12 16l10-6 10 6v14l-10 6-10-6z" fill="currentColor" opacity="0.3" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <path d="M22 10v16M12 16l10 6 10-6" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
  </>
  ),
  documents: (
  <>
    <path d="M14 8h12l6 6v20H14z" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <path d="M26 8v6h6" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <path d="M18 24h12M18 30h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  employees: (
  <>
    <circle cx="16" cy="16" r="5" fill="currentColor" />
    <circle cx="28" cy="18" r="4" fill="currentColor" opacity="0.7" />
    <path d="M8 34c0-5 3.6-8 8-8M22 34c0-4 2.8-6.5 6-6.5" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" />
    <rect x="30" y="28" width="8" height="8" rx="2" fill="currentColor" opacity="0.45" />
  </>
  ),
  attendance: (
  <>
    <circle cx="22" cy="22" r="12" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="2" />
    <path d="M22 14v9l6 4" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
  </>
  ),
  leave: (
  <>
    <rect x="10" y="12" width="24" height="22" rx="3" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="2" />
    <path d="M16 12v-2a2 2 0 012-2h8a2 2 0 012 2v2" stroke="currentColor" strokeWidth="2" />
    <path d="M14 24l4-4 4 4 6-8" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </>
  ),
  timesheets: (
  <>
    <rect x="8" y="10" width="28" height="24" rx="4" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="2" />
    <path d="M8 18h28M16 10v4M28 10v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <rect x="14" y="24" width="6" height="6" rx="1" fill="currentColor" />
    <rect x="24" y="24" width="6" height="6" rx="1" fill="currentColor" opacity="0.5" />
  </>
  ),
  payroll: (
  <>
    <rect x="10" y="14" width="24" height="18" rx="3" fill="currentColor" />
    <text x="22" y="27" textAnchor="middle" fontSize="10" fill="#fff" fontWeight="700">₹</text>
    <path d="M14 10h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  recruitment: (
  <>
    <rect x="12" y="10" width="20" height="26" rx="3" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="2" />
    <circle cx="22" cy="18" r="4" fill="currentColor" />
    <path d="M16 30c0-3 2.5-5 6-5s6 2 6 5" stroke="currentColor" strokeWidth="2" fill="none" />
  </>
  ),
  expenses: (
  <>
    <path d="M12 12h20l-2 22H14z" fill="currentColor" opacity="0.85" />
    <path d="M18 12V8h8v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <path d="M16 22h12" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  vendorBills: (
  <>
    <path d="M10 12h24v22H10z" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="2" />
    <path d="M15 20h14M15 26h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <circle cx="30" cy="16" r="4" fill="currentColor" />
  </>
  ),
  purchase: (
  <>
    <path d="M14 14h16l-2 18H16z" fill="currentColor" opacity="0.3" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <path d="M18 14V10h8v4" stroke="currentColor" strokeWidth="2" />
    <path d="M20 24h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  reports: (
  <>
    <path d="M10 30V18M18 30V12M26 30V20M34 30V8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    <path d="M8 32h28" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  inventory: (
  <>
    <path d="M8 18l14-8 14 8v14l-14 8-14-8z" fill="currentColor" opacity="0.3" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <path d="M22 10v16M8 18l14 8 14-8" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
  </>
  ),
  stock: (
  <>
    <path d="M10 20h24M10 26h16" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    <path d="M28 14l6 6-6 6" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M22 20h12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
  </>
  ),
  warehouse: (
  <>
    <path d="M8 20l14-10 14 10v14H8z" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <rect x="18" y="24" width="8" height="10" fill="currentColor" />
  </>
  ),
  approvals: (
  <>
    <circle cx="22" cy="22" r="12" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="2" />
    <path d="M15 22l5 5 9-10" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </>
  ),
  chat: (
  <>
    <path d="M10 12h24a2 2 0 012 2v10a2 2 0 01-2 2H20l-6 5v-5h-4a2 2 0 01-2-2V14a2 2 0 012-2z" fill="currentColor" opacity="0.85" />
  </>
  ),
  users: (
  <>
    <circle cx="15" cy="16" r="4" fill="currentColor" />
    <circle cx="29" cy="18" r="3.5" fill="currentColor" opacity="0.65" />
    <path d="M8 30c0-4 3-7 7-7M22 30c0-3.5 2.5-6 7-6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
    <path d="M30 10h6v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  user: (
  <>
    <circle cx="22" cy="15" r="6" fill="currentColor" />
    <path d="M12 32c0-5 4.5-9 10-9s10 4 10 9" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" />
  </>
  ),
  company: (
  <>
    <rect x="12" y="14" width="20" height="18" rx="2" fill="currentColor" opacity="0.3" stroke="currentColor" strokeWidth="2" />
    <path d="M18 14V10h8v4" stroke="currentColor" strokeWidth="2" />
    <rect x="18" y="22" width="8" height="10" fill="currentColor" />
  </>
  ),
  branding: (
  <>
    <rect x="10" y="12" width="24" height="18" rx="2" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="2" />
    <circle cx="22" cy="21" r="5" fill="currentColor" />
    <path d="M10 34h24" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  activity: (
  <>
    <path d="M12 10h16v24H12z" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="2" />
    <path d="M16 18h12M16 24h8M16 30h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  alerts: (
  <>
    <path d="M22 8a8 8 0 018 8v6l3 3H11l3-3v-6a8 8 0 018-8z" fill="currentColor" opacity="0.85" />
    <path d="M19 34a3 3 0 006 0" stroke="currentColor" strokeWidth="2" fill="none" />
  </>
  ),
  email: (
  <>
    <rect x="8" y="12" width="28" height="20" rx="3" fill="currentColor" opacity="0.25" stroke="currentColor" strokeWidth="2" />
    <path d="M8 14l14 10 14-10" stroke="currentColor" strokeWidth="2" fill="none" strokeLinejoin="round" />
  </>
  ),
  settings: (
  <>
    <circle cx="22" cy="22" r="6" fill="currentColor" opacity="0.3" stroke="currentColor" strokeWidth="2" />
    <path d="M22 8v4M22 32v4M8 22h4M32 22h4M12.5 12.5l2.8 2.8M28.7 28.7l2.8 2.8M31.5 12.5l-2.8 2.8M13.3 28.7l-2.8 2.8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  numbering: (
  <>
    <text x="12" y="28" fontSize="14" fill="currentColor" fontWeight="800">#</text>
    <path d="M22 14h12M22 22h8M22 30h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </>
  ),
  roles: (
  <>
    <rect x="10" y="10" width="11" height="11" rx="2" fill="currentColor" opacity="0.55" />
    <rect x="23" y="10" width="11" height="11" rx="2" fill="currentColor" opacity="0.75" />
    <rect x="10" y="23" width="11" height="11" rx="2" fill="currentColor" opacity="0.75" />
    <rect x="23" y="23" width="11" height="11" rx="2" fill="currentColor" />
  </>
  ),
};

function AppIcon({ name, color, size = 44 }) {
  const content = ICONS[name] || ICONS.documents;

  return (
    <span
      className="crm-app-icon"
      style={{ "--app-color": color, width: size, height: size }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 44 44" width={size} height={size} style={{ color }}>
        {content}
      </svg>
    </span>
  );
}

export default AppIcon;
