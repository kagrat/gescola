import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[] | null>(null);

  function reload() {
    api.get<Notification[]>("/me/notifications").then(setNotifications);
  }
  useEffect(reload, []);

  async function markRead(id: string) {
    await api.post(`/me/notifications/${id}/read`);
    reload();
  }

  return (
    <div className="px-10 py-10 max-w-2xl">
      <h1 className="font-display text-3xl font-medium text-ink">Notifications</h1>
      <p className="text-sm text-ink/55 mt-1">Relances et alertes concernant vos enfants.</p>

      <div className="mt-8 space-y-3">
        {notifications === null && <p className="text-sm text-ink/50">Chargement…</p>}
        {notifications && notifications.length === 0 && (
          <p className="text-sm text-ink/50">Aucune notification pour l'instant.</p>
        )}
        {notifications?.map((n) => (
          <div
            key={n.id}
            className={`border rounded p-4 ${n.read_at ? "border-line bg-white" : "border-ochre/40 bg-ochre/5"}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-ink text-[14.5px]">{n.title}</p>
                <p className="text-sm text-ink/60 mt-1">{n.body}</p>
                <p className="text-xs text-ink/40 mt-2">{new Date(n.created_at).toLocaleDateString("fr-FR")}</p>
              </div>
              {!n.read_at && (
                <button onClick={() => markRead(n.id)} className="text-xs text-navy underline underline-offset-2 hover:text-navy-light whitespace-nowrap">
                  Marquer lu
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
