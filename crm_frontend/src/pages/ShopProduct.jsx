import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import ShopShell from "../components/ShopShell";
import { formatINR, publicShopFetch } from "../utils/ecommerce";

function ShopProduct() {
  const { companySlug, productSlug } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [qty, setQty] = useState(1);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    publicShopFetch(companySlug, `/shop/products/${productSlug}`)
      .then(setProduct)
      .catch((err) => setError(err.message));
  }, [companySlug, productSlug]);

  const addToCart = async () => {
    setAdding(true);
    setError("");
    try {
      await publicShopFetch(companySlug, "/cart/items", {
        method: "POST",
        body: JSON.stringify({ product_id: product.id, quantity: qty }),
      });
      navigate(`/s/${companySlug}/cart`);
    } catch (err) {
      setError(err.message);
    } finally {
      setAdding(false);
    }
  };

  return (
    <ShopShell companySlug={companySlug} showStoreTitle={false}>
      <div className="crm-shop-content">
        <Link to={`/s/${companySlug}/shop`} className="crm-shop-back">← Back to shop</Link>
        {error && <p className="crm-error crm-mt">{error}</p>}
        {!product && !error && <p className="crm-shop-status crm-mt">Loading…</p>}
        {product && (
          <article className="crm-shop-product-detail crm-mt">
            <div className="crm-shop-product-media">
              {product.image_url ? (
                <img src={product.image_url} alt={product.name} className="crm-shop-product-image" loading="lazy" />
              ) : (
                <div className="crm-shop-card-placeholder crm-shop-product-image" aria-hidden="true" />
              )}
            </div>
            <div className="crm-shop-product-info">
              <h2 className="crm-shop-product-title">{product.name}</h2>
              {product.category && <p className="crm-shop-card-category">{product.category}</p>}
              <p className="crm-shop-price crm-mt">
                {formatINR(product.price)}
                <span className="crm-shop-gst-note"> + GST ({product.gst_rate}%)</span>
              </p>
              {product.description && <p className="crm-shop-product-desc">{product.description}</p>}
              {!product.in_stock ? (
                <p className="crm-shop-badge crm-shop-badge-warn crm-mt">Out of stock</p>
              ) : (
                <div className="crm-shop-add-row crm-mt">
                  <label className="crm-shop-qty-label" htmlFor="shop-qty">Qty</label>
                  <input
                    id="shop-qty"
                    type="number"
                    min={1}
                    max={99}
                    value={qty}
                    onChange={(e) => setQty(Number(e.target.value))}
                    className="crm-input crm-input-sm"
                  />
                  <button type="button" className="crm-btn crm-shop-add-btn" onClick={addToCart} disabled={adding}>
                    {adding ? "Adding…" : "Add to cart"}
                  </button>
                </div>
              )}
            </div>
          </article>
        )}
      </div>
    </ShopShell>
  );
}

export default ShopProduct;
