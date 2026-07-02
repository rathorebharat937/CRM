import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import ShopShell from "../components/ShopShell";
import { formatINR, publicShopFetch } from "../utils/ecommerce";

function ShopCart() {
  const { companySlug } = useParams();
  const navigate = useNavigate();
  const [cart, setCart] = useState(null);
  const [error, setError] = useState("");

  const load = () => {
    publicShopFetch(companySlug, "/cart").then(setCart).catch((err) => setError(err.message));
  };

  useEffect(() => { load(); }, [companySlug]);

  const updateQty = async (itemId, quantity) => {
    try {
      const data = await publicShopFetch(companySlug, `/cart/items/${itemId}`, {
        method: "PUT",
        body: JSON.stringify({ quantity }),
      });
      setCart(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const removeItem = async (itemId) => {
    try {
      const data = await publicShopFetch(companySlug, `/cart/items/${itemId}`, { method: "DELETE" });
      setCart(data);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <ShopShell companySlug={companySlug} showStoreTitle={false}>
      <div className="crm-shop-content">
        <h2 className="crm-shop-page-title">Your cart</h2>
        {error && <p className="crm-error">{error}</p>}
        {!cart && !error && <p className="crm-shop-status">Loading…</p>}
        {cart?.items?.length === 0 && (
          <div className="crm-shop-empty">
            <p className="crm-muted">Your cart is empty.</p>
            <Link to={`/s/${companySlug}/shop`} className="crm-btn crm-btn-sm crm-mt">Continue shopping</Link>
          </div>
        )}
        {cart?.items?.length > 0 && (
          <>
            <div className="crm-shop-cart-list crm-mt">
              {cart.items.map((item) => (
                <article key={item.id} className="crm-shop-cart-item">
                  <div className="crm-shop-cart-item-main">
                    <Link to={`/s/${companySlug}/shop/${item.product_slug}`} className="crm-shop-cart-item-name">
                      {item.product_name}
                    </Link>
                    <p className="crm-shop-cart-item-price">{formatINR(item.line_total)}</p>
                  </div>
                  <div className="crm-shop-cart-item-actions">
                    <label className="crm-shop-qty-label" htmlFor={`qty-${item.id}`}>Qty</label>
                    <input
                      id={`qty-${item.id}`}
                      type="number"
                      min={1}
                      max={99}
                      value={item.quantity}
                      onChange={(e) => updateQty(item.id, Number(e.target.value))}
                      className="crm-input crm-input-sm"
                    />
                    <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => removeItem(item.id)}>
                      Remove
                    </button>
                  </div>
                </article>
              ))}
            </div>
            <div className="crm-shop-summary crm-mt">
              <strong>Subtotal: {formatINR(cart.subtotal)}</strong>
              <button type="button" className="crm-btn crm-shop-checkout-btn" onClick={() => navigate(`/s/${companySlug}/checkout`)}>
                Checkout
              </button>
            </div>
          </>
        )}
      </div>
    </ShopShell>
  );
}

export default ShopCart;
