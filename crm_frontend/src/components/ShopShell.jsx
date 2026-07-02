import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PublicSiteShell } from "./WebsiteSectionRenderer";
import { fetchCompanyBranding, fetchShopInfo, publicShopFetch } from "../utils/ecommerce";

function ShopShell({ companySlug, children, showStoreTitle = true }) {
  const [company, setCompany] = useState(null);
  const [shopInfo, setShopInfo] = useState(null);
  const [cartCount, setCartCount] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([fetchCompanyBranding(companySlug), fetchShopInfo(companySlug)])
      .then(([branding, info]) => {
        setCompany(branding);
        setShopInfo(info);
        if (!info.is_enabled) setError("This store is not available.");
      })
      .catch((err) => setError(err.message));
  }, [companySlug]);

  useEffect(() => {
    if (!shopInfo?.is_enabled) return;
    publicShopFetch(companySlug, "/cart")
      .then((cart) => setCartCount(cart.item_count || 0))
      .catch(() => setCartCount(0));
  }, [companySlug, shopInfo?.is_enabled]);

  if (error) {
    return (
      <div className="crm-public-site">
        <div className="crm-shop-content"><p className="crm-error">{error}</p></div>
      </div>
    );
  }
  if (!company) {
    return (
      <div className="crm-public-site">
        <div className="crm-shop-content"><p>Loading…</p></div>
      </div>
    );
  }

  const headerActions = (
    <>
      <Link to={`/s/${companySlug}/account`} className="crm-btn crm-btn-sm crm-btn-outline">
        Account
      </Link>
      <Link to={`/s/${companySlug}/cart`} className="crm-btn crm-btn-sm crm-btn-inline">
        Cart{cartCount > 0 ? ` (${cartCount})` : ""}
      </Link>
    </>
  );

  return (
    <PublicSiteShell company={company} companySlug={companySlug} shopEnabled headerActions={headerActions}>
      <div className="crm-shop-layout">
        {showStoreTitle && (
          <div className="crm-shop-page-head">
            <h1 className="crm-shop-title">{shopInfo?.store_name || "Shop"}</h1>
          </div>
        )}
        {children}
      </div>
    </PublicSiteShell>
  );
}

export default ShopShell;
