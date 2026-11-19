import { useEffect, useState } from "react";
import api from "../../api/config";
import styles from "./EditStudent.module.css";

const fields = [
  ["surname", "Фамилия"],
  ["name", "Имя"],
  ["patronymic", "Отчество"],
  ["surname_latin", "Фамилия латиницей"],
  ["name_latin", "Имя латиницей"],
  ["email", "Email"],
  ["employee_id", "Табельный номер"],
];
function message(error) {
  const value = error.response?.data;
  return typeof value?.error === "string"
    ? value.error
    : value
      ? Object.entries(value)
          .map(
            ([key, val]) =>
              `${key}: ${Array.isArray(val) ? val.join(" ") : val}`,
          )
          .join(" ")
      : "Не удалось выполнить действие. Повторите попытку.";
}
export default function EditStudent() {
  const [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [page, setPage] = useState(1),
    [revision, setRevision] = useState(0);
  const [rows, setRows] = useState([]),
    [count, setCount] = useState(0),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [selected, setSelected] = useState(null),
    [form, setForm] = useState({}),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [credentials, setCredentials] = useState(null);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api
      .get("/api/execution/methodist/students/", {
        params: { search: query, page },
      })
      .then(({ data }) => {
        if (active) {
          setRows(data.results);
          setCount(data.count);
        }
      })
      .catch((e) => {
        if (active) setError(message(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query, page, revision]);
  function select(student) {
    setSelected(student);
    setForm(
      Object.fromEntries(fields.map(([key]) => [key, student[key] || ""])),
    );
    setCredentials(null);
    setNotice("");
    setError("");
  }
  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await api.patch(
        `/api/execution/methodist/students/${selected.id}/`,
        form,
      );
      setSelected(data);
      setRevision((v) => v + 1);
      setNotice("Личные данные сохранены. Назначения и оценки не изменены.");
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function reset() {
    if (
      busy ||
      !window.confirm(
        `Сбросить пароль слушателя «${selected.surname} ${selected.name}»? Текущие сессии входа будут отозваны. Временный пароль нужно передать лично.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    setCredentials(null);
    setNotice("");
    try {
      const { data } = await api.post(
        `/api/execution/methodist/students/${selected.id}/reset-password/`,
        { confirm: true },
      );
      setCredentials(data);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className={styles.page}>
      <h1>Редактировать слушателя</h1>
      <p>
        Исправление личных данных и восстановление доступа без изменения
        назначений.
      </p>
      <form
        className={styles.search}
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(search.trim());
          setPage(1);
          setSelected(null);
          setCredentials(null);
        }}
      >
        <input
          aria-label="Поиск слушателя"
          placeholder="ФИО, email, логин или табельный номер"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          disabled={busy}
        />
        <button disabled={busy}>Найти</button>
      </form>
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <div className={styles.grid}>
        <section aria-label="Найденные слушатели" className={styles.panel}>
          <p>Найдено: {count}</p>
          {loading ? (
            <p role="status">Загрузка…</p>
          ) : rows.length ? (
            rows.map((student) => (
              <button
                key={student.id}
                type="button"
                className={styles.person}
                aria-pressed={selected?.id === student.id}
                disabled={busy}
                onClick={() => select(student)}
              >
                <strong>
                  {student.surname} {student.name} {student.patronymic}
                </strong>
                <span>
                  {student.email || "Email не указан"} ·{" "}
                  {student.username || "Нет учётной записи"}
                </span>
                <span>
                  ID {student.id}
                  {student.employee_id
                    ? ` · Таб. № ${student.employee_id}`
                    : ""}
                </span>
              </button>
            ))
          ) : (
            <p>Слушатели не найдены.</p>
          )}
          <div className={styles.actions}>
            <button
              disabled={page === 1 || busy || loading}
              onClick={() => setPage((v) => v - 1)}
            >
              Назад
            </button>
            <span>Страница {page}</span>
            <button
              disabled={page * 15 >= count || busy || loading}
              onClick={() => setPage((v) => v + 1)}
            >
              Далее
            </button>
          </div>
        </section>
        <section aria-label="Карточка слушателя" className={styles.panel}>
          {selected ? (
            <>
              <h2>
                {selected.surname} {selected.name}
              </h2>
              <p>
                Постоянный ID: {selected.id} · Логин:{" "}
                {selected.username || "не назначен"}
              </p>
              <form onSubmit={save}>
                <fieldset disabled={busy}>
                  {fields.map(([key, label]) => (
                    <label key={key}>
                      {label}
                      <input
                        type={key === "email" ? "email" : "text"}
                        required={["surname", "name"].includes(key)}
                        value={form[key]}
                        onChange={(e) =>
                          setForm({ ...form, [key]: e.target.value })
                        }
                      />
                    </label>
                  ))}
                  <button type="submit">
                    {busy ? "Сохранение…" : "Сохранить личные данные"}
                  </button>
                </fieldset>
              </form>
              <hr />
              <h3>Доступ к системе</h3>
              <button
                disabled={busy || !selected.can_reset_password}
                onClick={reset}
              >
                Сбросить пароль
              </button>
              {!selected.can_reset_password && (
                <p>Сброс для этой учётной записи выполняет администратор.</p>
              )}
              {credentials && (
                <div role="status" className={styles.credentials}>
                  <strong>Передайте слушателю лично</strong>
                  <p>
                    Логин: <code>{credentials.username}</code>
                  </p>
                  <p>
                    Временный пароль:{" "}
                    <code>{credentials.temporary_password}</code>
                  </p>
                  <p>{credentials.message}</p>
                  <button onClick={() => setCredentials(null)}>
                    Скрыть пароль
                  </button>
                </div>
              )}
            </>
          ) : (
            <p>Найдите слушателя и выберите его карточку.</p>
          )}
        </section>
      </div>
    </section>
  );
}
