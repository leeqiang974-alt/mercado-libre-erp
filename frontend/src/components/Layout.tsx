import { FileText, Send, Store, Upload } from "lucide-react";
import type { ReactNode } from "react";

const tabs = [
  { id: "import", label: "Import", icon: Upload },
  { id: "drafts", label: "Drafts", icon: FileText },
  { id: "publishing", label: "Publish", icon: Send },
  { id: "stores", label: "Stores", icon: Store },
];

export function Layout({
  page,
  onPageChange,
  children,
}: {
  page: string;
  onPageChange: (page: string) => void;
  children: ReactNode;
}) {
  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Amazon Meli</h1>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              className={page === tab.id ? "active" : ""}
              key={tab.id}
              onClick={() => onPageChange(tab.id)}
              title={tab.label}
            >
              <Icon size={18} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </aside>
      <main>{children}</main>
    </div>
  );
}
