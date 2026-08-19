import { useEffect, useState } from "react";
import { MapPin, Phone } from "lucide-react";
import { listWarehouses, type WarehouseRecord } from "../api/erpClient";

export function WarehousePage() {
  const [warehouses, setWarehouses] = useState<WarehouseRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void listWarehouses()
      .then(setWarehouses)
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">库存管理</p>
          <h2>仓库管理</h2>
          <p>管理多仓库、库位、联系方式等基础信息。</p>
        </div>
      </header>

      {loading && <div className="empty-state">加载中...</div>}
      {!loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
          {warehouses.map((w) => (
            <div key={w.id} className="surface" style={{ padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                <div>
                  <h3 style={{ margin: "0 0 4px", fontSize: 18 }}>{w.name}</h3>
                  <span style={{ fontSize: 12, padding: "2px 8px", background: "#dbeafe", color: "#1d4ed8", borderRadius: 4 }}>
                    {w.code}
                  </span>
                </div>
                <MapPin size={20} style={{ color: "#2563eb" }} />
              </div>
              <p style={{ fontSize: 14, color: "#52606d", margin: "8px 0" }}>
                <MapPin size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
                {w.address}
              </p>
              <p style={{ fontSize: 14, color: "#52606d", margin: "8px 0" }}>
                <Phone size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
                {w.contact_name} · {w.contact_phone}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
