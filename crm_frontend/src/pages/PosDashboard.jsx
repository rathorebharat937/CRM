import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { ActionStatusMessages, ModuleNav, ModulePageHeader } from "../components/ModulePage";
import { apiFetch } from "../utils/api";
import { formatINR, getPosSessionId, setPosSessionId } from "../utils/pos";
import { hasPermission } from "../utils/permissions";

function PosDashboard() {
  const role = localStorage.getItem("role") || "Staff";
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [registers, setRegisters] = useState([]);
  const [error, setError] = useState("");
  const [opening, setOpening] = useState(false);
  const [registerId, setRegisterId] = useState("");
  const [floatAmt, setFloatAmt] = useState("2000");

  useEffect(() => {
    Promise.all([apiFetch("/pos/dashboard"), apiFetch("/pos/registers")])
      .then(([dash, regs]) => {
        setData(dash);
        setRegisters(regs);
        if (regs.length && !registerId) setRegisterId(String(regs[0].id));
      })
      .catch((err) => setError(err.message));
  }, [registerId]);

  const openSession = async () => {
    setOpening(true);
    setError("");
    try {
      const session = await apiFetch("/pos/sessions/open", {
        method: "POST",
        body: JSON.stringify({ register_id: Number(registerId), opening_float: Number(floatAmt) }),
      });
      setPosSessionId(session.id);
      navigate("/pos/terminal");
    } catch (err) {
      setError(err.message);
    } finally {
      setOpening(false);
    }
  };

  const resume = () => {
    const sid = getPosSessionId();
    if (sid) navigate("/pos/terminal");
    else setError("No active session. Open a register first.");
  };

  return (
    <DashboardLayout title="Point of Sale" roleLabel={role}>
      <div className="crm-panel">
        <ModulePageHeader subtitle="Counter billing and cash sessions">
          {hasPermission("pos.manage_settings") && (
            <Link to="/pos/settings" className="crm-btn crm-btn-sm crm-btn-outline">Settings</Link>
          )}
          {hasPermission("pos.bill") && (
            <>
              <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={resume}>Resume terminal</button>
              <button type="button" className="crm-btn crm-btn-sm" onClick={openSession} disabled={opening || !registerId}>
                {opening ? "Opening…" : "Open session"}
              </button>
            </>
          )}
        </ModulePageHeader>
        {hasPermission("pos.bill") && registers.length > 0 && (
          <div className="crm-form crm-form-narrow crm-mt">
            <div className="crm-form-field">
              <label>Register</label>
              <select value={registerId} onChange={(e) => setRegisterId(e.target.value)}>
                {registers.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}{r.has_open_session ? " (open)" : ""}</option>
                ))}
              </select>
            </div>
            <div className="crm-form-field">
              <label>Opening float (₹)</label>
              <input type="number" value={floatAmt} onChange={(e) => setFloatAmt(e.target.value)} />
            </div>
          </div>
        )}
        <ActionStatusMessages error={error} />
        {data && (
          <>
            <div className="crm-stats-grid crm-mt">
              <div className="crm-stat-card"><span className="crm-stat-value">{formatINR(data.sales_today)}</span><span className="crm-stat-label">Sales today</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.bills_today}</span><span className="crm-stat-label">Bills today</span></div>
              <div className="crm-stat-card"><span className="crm-stat-value">{data.open_sessions}</span><span className="crm-stat-label">Open sessions</span></div>
            </div>
            <ModuleNav>
              <Link to="/pos/bills" className="crm-btn crm-btn-sm crm-btn-outline">Bills</Link>
              <Link to="/pos/sessions" className="crm-btn crm-btn-sm crm-btn-outline">Sessions</Link>
              {hasPermission("pos.manage_catalog") && <Link to="/pos/catalog" className="crm-btn crm-btn-sm crm-btn-outline">Catalog</Link>}
            </ModuleNav>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default PosDashboard;
