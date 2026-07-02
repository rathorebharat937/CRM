import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import ShopShell from "../components/ShopShell";
import { emptyCheckoutForm, fetchShopInfo, formatINR, getStoreCustomerToken, publicShopFetch } from "../utils/ecommerce";

function ShopCheckout() {
  const { companySlug } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState(emptyCheckoutForm());
  const [cart, setCart] = useState(null);
  const [shopInfo, setShopInfo] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const loggedIn = Boolean(getStoreCustomerToken(companySlug));

  useEffect(() => {
    fetchShopInfo(companySlug)
      .then((info) => {
        setShopInfo(info);
        setForm(emptyCheckoutForm({
          payment_method: info.default_payment_method || "bank_transfer",
          payment_terms: info.default_payment_terms || "due_on_receipt",
        }));
      })
      .catch((err) => setError(err.message));

    publicShopFetch(companySlug, "/cart")
      .then((data) => {
        if (!data.items?.length) navigate(`/s/${companySlug}/cart`);
        setCart(data);
      })
      .catch((err) => setError(err.message));
  }, [companySlug, navigate]);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const setAddress = (prefix, key, value) => setForm((f) => ({ ...f, [prefix]: { ...f[prefix], [key]: value } }));

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const payload = {
        guest_name: form.guest_name || undefined,
        guest_email: form.guest_email || undefined,
        guest_phone: form.guest_phone || undefined,
        gstin: form.gstin || undefined,
        shipping_address: form.shipping_address,
        billing_address: form.billing_same ? undefined : form.billing_address,
        shipping_method: "pickup",
        payment_method: form.payment_method,
        payment_terms: form.payment_terms,
        customer_note: form.customer_note || undefined,
      };
      const result = await publicShopFetch(companySlug, "/checkout", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      navigate(`/s/${companySlug}/checkout/confirmation/${result.order_number}`, { state: { message: result.message } });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const paymentMethods = shopInfo?.payment_methods?.length
    ? shopInfo.payment_methods
    : [
        { value: "online", label: "Pay online (UPI / card / net banking)" },
        { value: "bank_transfer", label: "Bank transfer / UPI (against proforma invoice)" },
      ];
  const paymentTerms = shopInfo?.payment_terms?.length
    ? shopInfo.payment_terms
    : [
        { value: "due_on_receipt", label: "100% advance — due on receipt (work starts after payment)" },
        { value: "milestone_50_50", label: "50% advance, 50% on service completion" },
        { value: "net_15", label: "Net 15 days — invoice terms (B2B / GST registered)" },
      ];

  return (
    <ShopShell companySlug={companySlug} showStoreTitle={false}>
      <div className="crm-shop-content crm-shop-checkout">
        <h2 className="crm-shop-page-title">Checkout</h2>
        {error && <p className="crm-error">{error}</p>}
        <form className="crm-form crm-mt" onSubmit={submit}>
          {!loggedIn && (
            <>
              <h3>Contact</h3>
              <div className="crm-form-field"><label>Name *</label><input required value={form.guest_name} onChange={(e) => setField("guest_name", e.target.value)} /></div>
              <div className="crm-form-field"><label>Email *</label><input type="email" required value={form.guest_email} onChange={(e) => setField("guest_email", e.target.value)} /></div>
              <div className="crm-form-field"><label>Phone *</label><input required value={form.guest_phone} onChange={(e) => setField("guest_phone", e.target.value)} /></div>
            </>
          )}
          <h3>Billing address</h3>
          {["line1", "line2", "city", "state", "pincode"].map((key) => (
            <div className="crm-form-field" key={key}>
              <label>{key === "line1" ? "Address line 1 *" : key === "line2" ? "Address line 2" : key === "pincode" ? "PIN code *" : `${key[0].toUpperCase()}${key.slice(1)} *`}</label>
              <input
                required={key !== "line2"}
                pattern={key === "pincode" ? "\\d{6}" : undefined}
                value={form.shipping_address[key]}
                onChange={(e) => setAddress("shipping_address", key, e.target.value)}
              />
            </div>
          ))}
          <div className="crm-form-field">
            <label>GSTIN (optional, for B2B invoice)</label>
            <input value={form.gstin} onChange={(e) => setField("gstin", e.target.value)} />
          </div>
          <h3>Payment terms &amp; method</h3>
          <div className="crm-form-field">
            <label>Payment terms</label>
            <select value={form.payment_terms} onChange={(e) => setField("payment_terms", e.target.value)}>
              {paymentTerms.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="crm-form-field">
            <label>Payment method</label>
            <select value={form.payment_method} onChange={(e) => setField("payment_method", e.target.value)}>
              {paymentMethods.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          {form.payment_method === "bank_transfer" && shopInfo?.bank_details && (
            <div className="crm-shop-bank-details crm-mt">
              <p className="crm-muted"><strong>Bank / UPI details</strong></p>
              <pre className="crm-shop-bank-pre">{shopInfo.bank_details}</pre>
            </div>
          )}
          <div className="crm-form-field">
            <label>Notes for our team (optional)</label>
            <textarea rows={2} value={form.customer_note} onChange={(e) => setField("customer_note", e.target.value)} placeholder="Entity name, urgency, or engagement context" />
          </div>
          {cart && (
            <div className="crm-shop-summary crm-mt">
              <p>Service subtotal: {formatINR(cart.subtotal)}</p>
              <p className="crm-muted">GST included in final invoice. No shipping charges for online services.</p>
            </div>
          )}
          <button type="submit" className="crm-btn crm-mt" disabled={submitting}>{submitting ? "Placing order…" : "Place order"}</button>
        </form>
      </div>
    </ShopShell>
  );
}

export default ShopCheckout;
