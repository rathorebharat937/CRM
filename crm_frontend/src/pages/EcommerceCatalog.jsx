import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DashboardLayout from "../components/DashboardLayout";
import { apiFetch } from "../utils/api";
import { formatINR } from "../utils/ecommerce";

function EcommerceCatalog() {
  const role = localStorage.getItem("role") || "Staff";
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [imageUrl, setImageUrl] = useState("");

  const load = () =>
    apiFetch("/ecommerce/catalog")
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch((err) => setError(err.message));

  useEffect(() => { load(); }, []);

  const toggle = async (productId, sellOnline) => {
    try {
      await apiFetch(`/ecommerce/catalog/${productId}`, {
        method: "PUT",
        body: JSON.stringify({ sell_online: sellOnline }),
      });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const saveImage = async (productId) => {
    try {
      await apiFetch(`/ecommerce/catalog/${productId}`, {
        method: "PUT",
        body: JSON.stringify({ online_image_url: imageUrl.trim() || null }),
      });
      setEditingId(null);
      setImageUrl("");
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <DashboardLayout title="Online catalog" roleLabel={role}>
      <div className="crm-panel">
        <Link to="/ecommerce" className="crm-muted">← Online Store</Link>
        <p className="crm-meta-sub crm-mt">
          Enable products for the public shop and set an image URL (HTTPS link to a JPG/PNG/WebP).
        </p>
        {error && <p className="crm-error crm-mt">{error}</p>}
        <div className="crm-table-wrap crm-mt">
          <table className="crm-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Image</th>
                <th>Price</th>
                <th>Sell online</th>
                <th>Slug</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>
                    {editingId === p.id ? (
                      <div className="crm-shop-catalog-image-edit">
                        <input
                          value={imageUrl}
                          onChange={(e) => setImageUrl(e.target.value)}
                          placeholder="https://…/product.jpg"
                          className="crm-input"
                        />
                        <button type="button" className="crm-btn crm-btn-sm crm-btn-inline" onClick={() => saveImage(p.id)}>Save</button>
                        <button type="button" className="crm-btn crm-btn-sm crm-btn-outline" onClick={() => { setEditingId(null); setImageUrl(""); }}>Cancel</button>
                      </div>
                    ) : (
                      <div className="crm-shop-catalog-image-cell">
                        {p.online_image_url ? (
                          <img src={p.online_image_url} alt="" className="crm-shop-catalog-thumb" />
                        ) : (
                          <span className="crm-muted">Default</span>
                        )}
                        <button
                          type="button"
                          className="crm-link crm-btn-link"
                          onClick={() => { setEditingId(p.id); setImageUrl(p.online_image_url || ""); }}
                        >
                          Edit
                        </button>
                      </div>
                    )}
                  </td>
                  <td>{formatINR(p.price)}</td>
                  <td>
                    <input type="checkbox" checked={p.sell_online} onChange={(e) => toggle(p.id, e.target.checked)} />
                  </td>
                  <td>{p.online_slug || "—"}</td>
                  <td>{p.public_url && <a href={p.public_url} target="_blank" rel="noreferrer">Preview</a>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default EcommerceCatalog;
