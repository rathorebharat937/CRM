import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import ShopShell from "../components/ShopShell";
import { formatINR, publicShopFetch } from "../utils/ecommerce";

function ShopCatalog() {
  const { companySlug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const q = searchParams.get("q") || "";
  const category = searchParams.get("category") || "";

  useEffect(() => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (category) params.set("category", category);
    const qs = params.toString();
    publicShopFetch(companySlug, `/shop/products${qs ? `?${qs}` : ""}`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [companySlug, q, category]);

  const setCategory = (nextCategory) => {
    const params = {};
    if (q) params.q = q;
    if (nextCategory) params.category = nextCategory;
    setSearchParams(params);
  };

  return (
    <ShopShell companySlug={companySlug}>
      <div className="crm-shop-content">
        <form
          className="crm-shop-filters"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.target;
            setSearchParams({ q: form.q.value, ...(category ? { category } : {}) });
          }}
        >
          <input
            name="q"
            defaultValue={q}
            placeholder="Search products…"
            className="crm-input"
            aria-label="Search products"
          />
          <button type="submit" className="crm-btn crm-btn-sm">Search</button>
        </form>

        {data?.categories?.length > 0 && (
          <div className="crm-shop-categories" role="tablist" aria-label="Product categories">
            <button
              type="button"
              role="tab"
              aria-selected={!category}
              className={`crm-btn crm-btn-sm ${!category ? "crm-btn-inline" : "crm-btn-outline"}`}
              onClick={() => setCategory("")}
            >
              All
            </button>
            {data.categories.map((cat) => (
              <button
                key={cat}
                type="button"
                role="tab"
                aria-selected={category === cat}
                className={`crm-btn crm-btn-sm ${category === cat ? "crm-btn-inline" : "crm-btn-outline"}`}
                onClick={() => setCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        )}

        {error && <p className="crm-error">{error}</p>}
        {!data && !error && <p className="crm-shop-status">Loading products…</p>}
        {data?.items?.length === 0 && <p className="crm-shop-status crm-muted">No products available.</p>}

        <div className="crm-shop-grid">
          {data?.items?.map((product) => (
            <Link key={product.id} to={`/s/${companySlug}/shop/${product.slug}`} className="crm-shop-card">
              <div className="crm-shop-card-media">
                {product.image_url ? (
                  <img src={product.image_url} alt={product.name} className="crm-shop-card-image" loading="lazy" />
                ) : (
                  <div className="crm-shop-card-placeholder" aria-hidden="true" />
                )}
              </div>
              <div className="crm-shop-card-body">
                <h3 className="crm-shop-card-title">{product.name}</h3>
                {product.category && <p className="crm-shop-card-category">{product.category}</p>}
                <p className="crm-shop-price">
                  {formatINR(product.price)}
                  {product.compare_at_price && product.compare_at_price > product.price && (
                    <span className="crm-shop-compare">{formatINR(product.compare_at_price)}</span>
                  )}
                </p>
                {!product.in_stock && <span className="crm-shop-badge crm-shop-badge-warn">Out of stock</span>}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </ShopShell>
  );
}

export default ShopCatalog;
