import type { ReactNode } from "react";
import { Construction } from "lucide-react";

export function ComingSoonPage({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">即将上线</p>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </header>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "80px 20px",
          background: "white",
          border: "1px solid #dde3ea",
          borderRadius: "12px",
          color: "#52606d",
          textAlign: "center",
        }}
      >
        <Construction size={48} style={{ color: "#2563eb", marginBottom: 16 }} />
        <h3 style={{ margin: "0 0 8px", fontSize: 20 }}>模块开发中</h3>
        <p style={{ margin: 0, maxWidth: 400 }}>
          {children ?? "该模块正在紧张开发中，敬请期待。如需优先开发此模块，请联系管理员。"}
        </p>
      </div>
    </section>
  );
}
