import { MessageSquare, Mail } from "lucide-react";

export function MessagesPage() {
  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">客户服务</p>
          <h2>消息中心</h2>
          <p>处理美客多买家消息、站内信和售后问题。</p>
        </div>
      </header>

      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 20px", background: "white", border: "1px solid #dde3ea", borderRadius: 12, color: "#52606d", textAlign: "center" }}>
        <MessageSquare size={48} style={{ color: "#2563eb", marginBottom: 16 }} />
        <h3 style={{ margin: "0 0 8px", fontSize: 20 }}>消息中心开发中</h3>
        <p style={{ margin: 0, maxWidth: 400 }}>
          该模块将支持美客多买家消息汇总、自动回复模板、售后纠纷处理、评价管理等功能。
        </p>
      </div>
    </section>
  );
}
