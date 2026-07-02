import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { PublicSiteShell } from "../components/WebsiteSectionRenderer";
import { publicApiPath } from "../utils/api";

async function publicFetch(path) {
  const response = await fetch(publicApiPath(path));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Not found");
  return data;
}

function PublicBlog() {
  const { companySlug, postSlug } = useParams();
  const [searchParams] = useSearchParams();
  const preview = searchParams.get("preview");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (postSlug) {
      publicFetch(`/public/${companySlug}/blog/${postSlug}${preview ? `?preview=${preview}` : ""}`)
        .then(setData)
        .catch((err) => setError(err.message));
    } else {
      publicFetch(`/public/${companySlug}/blog`)
        .then(setData)
        .catch((err) => setError(err.message));
    }
  }, [companySlug, postSlug, preview]);

  if (error) {
    return <div className="crm-public-site"><div className="crm-panel"><p className="crm-error">{error}</p></div></div>;
  }
  if (!data) {
    return <div className="crm-public-site"><div className="crm-panel"><p>Loading…</p></div></div>;
  }

  if (postSlug && data.post) {
    const { post, company } = data;
    return (
      <PublicSiteShell company={company} companySlug={companySlug} preview={post.status !== "published"}>
        <article className="crm-website-section crm-website-blog-post">
          {post.cover_image_url && <img src={post.cover_image_url} alt="" className="crm-website-blog-cover" />}
          <h1>{post.title}</h1>
          {post.excerpt && <p className="crm-website-lead">{post.excerpt}</p>}
          <div className="crm-website-rich" dangerouslySetInnerHTML={{ __html: post.body_html }} />
        </article>
      </PublicSiteShell>
    );
  }

  const { company, posts } = data;
  return (
    <PublicSiteShell company={company} companySlug={companySlug}>
      <section className="crm-website-section">
        <h1>Blog</h1>
        {posts.length === 0 ? (
          <p className="crm-muted">No posts published yet.</p>
        ) : (
          <div className="crm-website-blog-list">
            {posts.map((post) => (
              <article key={post.id} className="crm-website-card">
                <h2><Link to={`/s/${companySlug}/blog/${post.slug}`}>{post.title}</Link></h2>
                {post.published_at && <p className="crm-muted">{new Date(post.published_at).toLocaleDateString()}</p>}
              </article>
            ))}
          </div>
        )}
      </section>
    </PublicSiteShell>
  );
}

export default PublicBlog;
