import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import WebsiteSectionRenderer, { PublicSiteShell } from "../components/WebsiteSectionRenderer";
import { publicApiPath } from "../utils/api";
import { fetchShopInfo } from "../utils/ecommerce";

async function publicFetch(path) {
  const response = await fetch(publicApiPath(path));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Page not found");
  return data;
}

function PublicSite() {
  const { companySlug, pageSlug } = useParams();
  const [searchParams] = useSearchParams();
  const preview = searchParams.get("preview");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [shopEnabled, setShopEnabled] = useState(false);

  useEffect(() => {
    fetchShopInfo(companySlug).then((info) => setShopEnabled(info.is_enabled)).catch(() => setShopEnabled(false));
  }, [companySlug]);

  useEffect(() => {
    const path = pageSlug
      ? `/public/${companySlug}/pages/${pageSlug}${preview ? `?preview=${preview}` : ""}`
      : `/public/${companySlug}${preview ? `?preview=${preview}` : ""}`;
    publicFetch(path).then(setData).catch((err) => setError(err.message));
  }, [companySlug, pageSlug, preview]);

  useEffect(() => {
    if (!data?.page) return;
    const title = data.page.seo_title || data.page.title;
    document.title = title;
    return () => { document.title = "BlackPapers CRM"; };
  }, [data]);

  if (error) {
    return <div className="crm-public-site"><div className="crm-panel"><p className="crm-error">{error}</p></div></div>;
  }
  if (!data) {
    return <div className="crm-public-site"><div className="crm-panel"><p>Loading…</p></div></div>;
  }

  const { page, company, forms, products } = data;
  const isPreview = Boolean(preview) || page.status !== "published";

  return (
    <PublicSiteShell company={company} companySlug={companySlug} preview={isPreview} shopEnabled={shopEnabled}>
      {(page.sections_json || []).map((section) => (
        <WebsiteSectionRenderer
          key={section.id}
          section={section}
          company={company}
          companySlug={companySlug}
          forms={forms}
          products={products}
        />
      ))}
    </PublicSiteShell>
  );
}

export default PublicSite;
