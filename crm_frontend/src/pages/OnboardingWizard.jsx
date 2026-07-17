import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiFetch, getAuthHeaders } from "../utils/api";

const STEPS = ["Company profile", "GST & address", "Invite team"];

const INDIAN_STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
  "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
  "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry", "Chandigarh",
];

function OnboardingWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [company, setCompany] = useState(null);
  const [invite, setInvite] = useState({ name: "", email: "", role: "Sales", password: "" });

  useEffect(() => {
    apiFetch("/admin/company")
      .then((data) => {
        setCompany(data);
        if (data.gstin && data.address_line1) {
          setStep(2);
        } else if (data.address_line1 || data.gstin) {
          setStep(1);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const updateCompany = async (payload) => {
    setError("");
    const updated = await apiFetch("/admin/company", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    setCompany(updated);
    return updated;
  };

  const finish = () => {
    localStorage.setItem("onboarding_complete", "1");
    navigate("/admin-dashboard");
  };

  const handleProfileStep = async (e) => {
    e.preventDefault();
    const form = e.target;
    try {
      await updateCompany({
        legal_name: form.legal_name.value,
        display_name: form.display_name.value,
        email: form.email.value || null,
        phone: form.phone.value || null,
        website: form.website.value || null,
        description: form.description.value || null,
        address_line1: company?.address_line1 || null,
        address_line2: company?.address_line2 || null,
        city: company?.city || null,
        state: company?.state || null,
        pincode: company?.pincode || null,
        country: company?.country || "India",
        gstin: company?.gstin || null,
        pan: company?.pan || null,
        currency: company?.currency || "INR",
        financial_year_start_month: company?.financial_year_start_month || 4,
        timezone: company?.timezone || "Asia/Kolkata",
      });
      setStep(1);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleGstStep = async (e) => {
    e.preventDefault();
    const form = e.target;
    try {
      await updateCompany({
        legal_name: company.legal_name,
        display_name: company.display_name,
        email: company.email,
        phone: company.phone,
        website: company.website,
        description: company.description,
        address_line1: form.address_line1.value || null,
        address_line2: form.address_line2.value || null,
        city: form.city.value || null,
        state: form.state.value || null,
        pincode: form.pincode.value || null,
        country: form.country.value || "India",
        gstin: form.gstin.value || null,
        pan: form.pan.value || null,
        currency: company.currency,
        financial_year_start_month: company.financial_year_start_month,
        timezone: company.timezone,
      });
      setStep(2);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!invite.email.trim()) {
      finish();
      return;
    }
    setError("");
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL || "http://localhost:8000"}/admin/users`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          name: invite.name,
          email: invite.email,
          password: invite.password,
          role: invite.role,
          status: "active",
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not invite user");
      }
      finish();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="crm-card crm-card-wide">
        <p className="crm-muted">Loading your workspace…</p>
      </div>
    );
  }

  return (
    <div className="crm-card crm-card-wide">
      <h2>Set up {company?.display_name || "your workspace"}</h2>
      <p className="crm-muted crm-mb">
        Step {step + 1} of {STEPS.length}: {STEPS[step]}
      </p>

      <div className="crm-onboarding-steps">
        {STEPS.map((label, idx) => (
          <span
            key={label}
            className={`crm-onboarding-step${idx === step ? " is-active" : idx < step ? " is-done" : ""}`}
          >
            {label}
          </span>
        ))}
      </div>

      {error && <p className="crm-error">{error}</p>}

      {step === 0 && company && (
        <form onSubmit={handleProfileStep} className="crm-form">
          <label htmlFor="legal_name">Legal name</label>
          <input id="legal_name" name="legal_name" defaultValue={company.legal_name} required />

          <label htmlFor="display_name">Display name</label>
          <input id="display_name" name="display_name" defaultValue={company.display_name} required />

          <label htmlFor="email">Company email</label>
          <input id="email" name="email" type="email" defaultValue={company.email || ""} />

          <label htmlFor="phone">Phone</label>
          <input id="phone" name="phone" defaultValue={company.phone || ""} />

          <label htmlFor="website">Website</label>
          <input id="website" name="website" defaultValue={company.website || ""} />

          <label htmlFor="description">About (optional)</label>
          <textarea id="description" name="description" rows={3} defaultValue={company.description || ""} />

          <button type="submit" className="crm-btn crm-btn-primary">Continue</button>
        </form>
      )}

      {step === 1 && company && (
        <form onSubmit={handleGstStep} className="crm-form">
          <label htmlFor="gstin">GSTIN (optional)</label>
          <input id="gstin" name="gstin" defaultValue={company.gstin || ""} placeholder="22AAAAA0000A1Z5" />

          <label htmlFor="pan">PAN (optional)</label>
          <input id="pan" name="pan" defaultValue={company.pan || ""} placeholder="AAAAA9999A" />

          <label htmlFor="address_line1">Address line 1</label>
          <input id="address_line1" name="address_line1" defaultValue={company.address_line1 || ""} />

          <label htmlFor="address_line2">Address line 2</label>
          <input id="address_line2" name="address_line2" defaultValue={company.address_line2 || ""} />

          <label htmlFor="city">City</label>
          <input id="city" name="city" defaultValue={company.city || ""} />

          <label htmlFor="state">State</label>
          <select id="state" name="state" defaultValue={company.state || ""}>
            <option value="">Select state</option>
            {INDIAN_STATES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <label htmlFor="pincode">Pincode</label>
          <input id="pincode" name="pincode" defaultValue={company.pincode || ""} />

          <label htmlFor="country">Country</label>
          <input id="country" name="country" defaultValue={company.country || "India"} />

          <div className="crm-form-actions">
            <button type="button" className="crm-btn crm-btn-ghost" onClick={() => setStep(0)}>Back</button>
            <button type="submit" className="crm-btn crm-btn-primary">Continue</button>
          </div>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={handleInvite} className="crm-form">
          <p className="crm-muted">
            Invite your first team member now, or skip and do this later from Admin → Users.
          </p>

          <label htmlFor="invite-name">Name</label>
          <input
            id="invite-name"
            value={invite.name}
            onChange={(e) => setInvite({ ...invite, name: e.target.value })}
          />

          <label htmlFor="invite-email">Email</label>
          <input
            id="invite-email"
            type="email"
            value={invite.email}
            onChange={(e) => setInvite({ ...invite, email: e.target.value })}
          />

          <label htmlFor="invite-role">Role</label>
          <select
            id="invite-role"
            value={invite.role}
            onChange={(e) => setInvite({ ...invite, role: e.target.value })}
          >
            <option value="Sales">Sales</option>
            <option value="Accountant">Accountant</option>
            <option value="Manager">Manager</option>
            <option value="Employee">Employee</option>
          </select>

          <label htmlFor="invite-password">Temporary password</label>
          <input
            id="invite-password"
            type="password"
            minLength={6}
            value={invite.password}
            onChange={(e) => setInvite({ ...invite, password: e.target.value })}
          />

          <div className="crm-form-actions">
            <button type="button" className="crm-btn crm-btn-ghost" onClick={() => setStep(1)}>Back</button>
            <button type="button" className="crm-btn crm-btn-outline" onClick={finish}>Skip for now</button>
            <button type="submit" className="crm-btn crm-btn-primary">Invite & go to dashboard</button>
          </div>
        </form>
      )}

      <Link to="/admin-dashboard" className="crm-link crm-mt">
        Skip setup and open dashboard
      </Link>
    </div>
  );
}

export default OnboardingWizard;
