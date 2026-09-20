import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";

interface Book {
  id: string;
  title: string;
  author: string;
  total_copies: number;
  available_copies: number;
}
interface Student {
  id: string;
  first_name: string;
  last_name: string;
}

export default function LibraryPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [showBookForm, setShowBookForm] = useState(false);
  const [showLoanForm, setShowLoanForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function reload() {
    api.get<Book[]>("/library/books").then(setBooks);
    api.get<Student[]>("/students").then(setStudents);
  }
  useEffect(reload, []);

  async function handleCreateBook(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/library/books", {
        title: form.get("title"), author: form.get("author"), total_copies: Number(form.get("total_copies") || 1),
      });
      setShowBookForm(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'ajouter l'ouvrage.");
    }
  }

  async function handleLoan(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.post("/library/loans", {
        book_id: form.get("book_id"), student_id: form.get("student_id"), due_at: form.get("due_at"),
      });
      setSuccess("Emprunt enregistré.");
      setShowLoanForm(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer l'emprunt.");
    }
  }

  return (
    <div className="px-10 py-10 max-w-3xl">
      <h1 className="font-display text-3xl font-medium text-ink">Bibliothèque</h1>
      <p className="text-sm text-ink/55 mt-1">Catalogue et emprunts.</p>

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg text-ink">Ouvrages</h2>
          <div className="flex gap-2">
            <button onClick={() => setShowLoanForm((v) => !v)} className="rounded border border-navy text-navy text-sm font-medium px-3.5 py-2 hover:bg-navy/5 transition">
              {showLoanForm ? "Annuler" : "Enregistrer un emprunt"}
            </button>
            <button onClick={() => setShowBookForm((v) => !v)} className="rounded bg-navy text-paper text-sm font-medium px-3.5 py-2 hover:bg-navy-light transition">
              {showBookForm ? "Annuler" : "+ Ouvrage"}
            </button>
          </div>
        </div>

        {showBookForm && (
          <form onSubmit={handleCreateBook} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
            <TextField name="title" label="Titre" required />
            <TextField name="author" label="Auteur" required />
            <TextField name="total_copies" label="Exemplaires" type="number" min="1" placeholder="1" />
            {error && <p className="sm:col-span-3 text-sm text-brick">{error}</p>}
            <div className="sm:col-span-3">
              <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                Ajouter au catalogue
              </button>
            </div>
          </form>
        )}

        {showLoanForm && (
          <form onSubmit={handleLoan} className="mt-4 border border-line rounded bg-white p-5 grid sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-1.5">Ouvrage</label>
              <select name="book_id" required className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
                <option value="">—</option>
                {books.map((b) => <option key={b.id} value={b.id} disabled={b.available_copies === 0}>{b.title} {b.available_copies === 0 ? "(indisponible)" : ""}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-1.5">Élève</label>
              <select name="student_id" required className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy">
                <option value="">—</option>
                {students.map((s) => <option key={s.id} value={s.id}>{s.first_name} {s.last_name}</option>)}
              </select>
            </div>
            <TextField name="due_at" label="À rendre le" type="date" required />
            {error && <p className="sm:col-span-3 text-sm text-brick">{error}</p>}
            {success && <p className="sm:col-span-3 text-sm text-pass">{success}</p>}
            <div className="sm:col-span-3">
              <button type="submit" className="rounded bg-ochre text-navy-deep text-sm font-medium px-4 py-2 hover:bg-ochre-dark transition">
                Enregistrer l'emprunt
              </button>
            </div>
          </form>
        )}

        <div className="mt-4 border border-line rounded bg-white overflow-hidden">
          <table className="w-full text-[14.5px]">
            <thead>
              <tr>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Titre</th>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Auteur</th>
                <th className="text-left text-[11.5px] font-semibold text-ink/40 uppercase tracking-wide px-4 pb-2.5 pt-4 border-b border-line">Disponibilité</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {books.length === 0 && <tr><td colSpan={3} className="px-4 py-6 text-ink/50">Aucun ouvrage.</td></tr>}
              {books.map((b) => (
                <tr key={b.id}>
                  <td className="px-4 py-2.5 text-ink">{b.title}</td>
                  <td className="px-4 py-2.5 text-ink/70">{b.author}</td>
                  <td className={`px-4 py-2.5 font-medium ${b.available_copies > 0 ? "text-pass" : "text-brick"}`}>
                    {b.available_copies} / {b.total_copies}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function TextField({ name, label, type = "text", required, placeholder, min }: { name: string; label: string; type?: string; required?: boolean; placeholder?: string; min?: string }) {
  return (
    <div>
      <label className="block text-sm font-medium text-ink/80 mb-1.5">{label}</label>
      <input name={name} type={type} required={required} placeholder={placeholder} min={min}
        className="w-full rounded border border-line bg-white px-3 py-2 text-[14.5px] focus:outline-none focus:ring-2 focus:ring-navy/30 focus:border-navy transition" />
    </div>
  );
}
