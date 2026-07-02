import { useState } from "react";
import { Link } from "react-router-dom";

import { publicApiPath } from "../utils/api";
import { SECTION_LABELS } from "../utils/website";

function formatAddress(company) {
  return [company.address_line1, company.address_line2, company.city, company.state, company.pincode, company.country]
    .filter(Boolean)
    .join(", ");
}

function PublicForm({ form, companySlug, onSuccess }) {
  const [values, setValues] = useState({});
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [message, setMessage] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const response = await fetch(publicApiPath(`/public/${companySlug}/forms/${form.slug}/submit`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fields: values, website_trap: values.website_trap || "" }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Submission failed");
      setDone(true);
      setMessage(data.message || "Thank you!");
      onSuccess?.(data);
    } catch (err) {
      setError(err.message);
    }
  };

  if (done) {
    return <p className="crm-success">{message}</p>;
  }

  return (
    <form className="crm-form crm-website-form" onSubmit={submit}>
      {(form.fields_json || []).map((field) => {
        if (field.type === "hidden" || field.key === "website_trap") {
          return (
            <input
              key={field.key}
              type="hidden"
              name={field.key}
              value={values[field.key] || ""}
              onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
              tabIndex={-1}
              autoComplete="off"
            />
          );
        }
        const common = {
          id: field.key,
          required: field.required,
          value: values[field.key] || "",
          onChange: (e) => setValues((v) => ({ ...v, [field.key]: e.target.value })),
        };
        return (
          <div className="crm-form-field" key={field.key}>
            <label htmlFor={field.key}>{field.label}{field.required ? " *" : ""}</label>
            {field.type === "textarea" ? (
              <textarea {...common} rows={4} placeholder={field.placeholder || ""} />
            ) : (
              <input
                {...common}
                type={field.type === "phone" ? "tel" : field.type}
                placeholder={field.placeholder || (field.type === "phone" ? "+91" : "")}
              />
            )}
          </div>
        );
      })}
      {error && <p className="crm-error">{error}</p>}
      <button type="submit" className="crm-btn">Submit enquiry</button>
    </form>
  );
}

export default function WebsiteSectionRenderer({ section, company, companySlug, forms, products }) {
  const props = section.props || {};

  switch (section.type) {
    case "hero":
      return (
        <section className="crm-website-hero" style={props.image_url ? { backgroundImage: `url(${props.image_url})` } : undefined}>
          <div className="crm-website-hero-inner">
            <h1>{props.headline}</h1>
            {props.subheadline && <p className="crm-website-lead">{props.subheadline}</p>}
            {props.cta_label && (
              props.cta_link ? (
                <a href={props.cta_link} className="crm-btn">{props.cta_label}</a>
              ) : (
                <span className="crm-btn">{props.cta_label}</span>
              )
            )}
          </div>
        </section>
      );
    case "rich_text":
      return (
        <section className="crm-website-section">
          {props.title && <h2>{props.title}</h2>}
          <div className="crm-website-rich" dangerouslySetInnerHTML={{ __html: props.body || "" }} />
        </section>
      );
    case "image":
      return (
        <section className="crm-website-section crm-website-image">
          {props.image_url && <img src={props.image_url} alt={props.alt_text || ""} />}
          {props.caption && <p className="crm-muted">{props.caption}</p>}
        </section>
      );
    case "services_grid":
      return (
        <section className="crm-website-section">
          {props.title && <h2>{props.title}</h2>}
          <div className="crm-website-grid">
            {(products || []).slice(0, props.limit || 3).map((p) => (
              <article key={p.id} className="crm-website-card">
                <h3>{p.name}</h3>
                {p.description && <p>{p.description}</p>}
                {p.price != null && <p className="crm-website-price">₹{p.price.toLocaleString("en-IN")}</p>}
              </article>
            ))}
          </div>
        </section>
      );
    case "testimonials":
      return (
        <section className="crm-website-section">
          {props.title && <h2>{props.title}</h2>}
          <div className="crm-website-grid">
            {(props.items || []).map((item, i) => (
              <blockquote key={i} className="crm-website-card">
                <p>"{item.quote}"</p>
                <footer>{item.name}{item.role ? ` — ${item.role}` : ""}</footer>
              </blockquote>
            ))}
          </div>
        </section>
      );
    case "faq":
      return (
        <section className="crm-website-section">
          {props.title && <h2>{props.title}</h2>}
          <div className="crm-website-faq">
            {(props.items || []).map((item, i) => (
              <details key={i} className="crm-website-faq-item">
                <summary>{item.question}</summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </section>
      );
    case "cta_banner":
      return (
        <section className="crm-website-cta">
          <h2>{props.headline}</h2>
          {props.button_label && (
            props.link ? <a href={props.link} className="crm-btn crm-btn-outline">{props.button_label}</a> : <span className="crm-btn crm-btn-outline">{props.button_label}</span>
          )}
        </section>
      );
    case "form_embed": {
      const form = (forms || []).find((f) => f.id === props.form_id);
      if (!form) return <section className="crm-website-section"><p className="crm-muted">Form not configured</p></section>;
      return (
        <section className="crm-website-section">
          <h2>{form.name}</h2>
          <PublicForm form={form} companySlug={companySlug} />
        </section>
      );
    }
    case "contact_info":
      return (
        <section className="crm-website-section crm-website-contact">
          <h2>Contact us</h2>
          <p><strong>{company.display_name}</strong></p>
          {company.phone && <p>Phone: <a href={`tel:${company.phone}`}>{company.phone}</a></p>}
          {company.email && <p>Email: <a href={`mailto:${company.email}`}>{company.email}</a></p>}
          {company.gstin && <p>GSTIN: {company.gstin}</p>}
          {formatAddress(company) && <p>{formatAddress(company)}</p>}
        </section>
      );
    case "spacer":
      return <div className={`crm-website-spacer crm-website-spacer-${props.size || "md"}`} aria-hidden="true" />;
    default:
      return (
        <section className="crm-website-section">
          <p className="crm-muted">{SECTION_LABELS[section.type] || section.type}</p>
        </section>
      );
  }
}

export function PublicSiteShell({ company, companySlug, children, preview, shopEnabled, headerActions }) {
  return (
    <div className="crm-public-site">
      {preview && (
        <div className="crm-website-preview-banner">Preview — not published</div>
      )}
      <header className="crm-public-site-header">
        <div className="crm-public-site-brand">
          {company.logo_filename && (
            <img src={publicApiPath(`/files/logo/${company.logo_filename}`)} alt="" className="crm-public-site-logo" />
          )}
          <Link to={`/s/${companySlug}`} className="crm-public-site-brand-name">
            {company.display_name}
          </Link>
        </div>
        <div className="crm-public-site-header-end">
          <nav className="crm-public-site-nav" aria-label="Site">
            <Link to={`/s/${companySlug}`}>Home</Link>
            <Link to={`/s/${companySlug}/blog`}>Blog</Link>
            {shopEnabled && <Link to={`/s/${companySlug}/shop`}>Shop</Link>}
          </nav>
          {headerActions ? <div className="crm-public-site-actions">{headerActions}</div> : null}
        </div>
      </header>
      <main className="crm-public-site-main">{children}</main>
      <footer className="crm-public-site-footer">
        <p>{company.display_name} · {company.city || company.country}</p>
        {company.website && <p>{company.website}</p>}
      </footer>
    </div>
  );
}
