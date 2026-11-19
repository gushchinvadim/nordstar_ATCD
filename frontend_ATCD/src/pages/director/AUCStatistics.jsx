import { useEffect, useRef, useState } from 'react';
import api from '../../api/config';
import styles from './AUCStatistics.module.css';

const fundingColumns = [
    ['self_paid', 'Физлица'],
    ['company_internal', 'НордСтар'],
    ['company_external', 'Внешние заказчики'],
    ['unspecified', 'Не указано'],
];
const number = new Intl.NumberFormat('ru-RU');
function dateLabel(value) {
    return value.split('-').reverse().join('.');
}
function errorText(error) {
    const data = error.response?.data;
    if (!data) return 'Не удалось загрузить статистику. Повторите попытку.';
    const labels = {
        date_from: 'Дата начала',
        date_to: 'Дата окончания',
        non_field_errors: 'Период',
        detail: 'Доступ',
    };
    return Object.entries(data)
        .map(
            ([key, value]) =>
                `${labels[key] || key}: ${Array.isArray(value) ? value.join(' ') : value}`,
        )
        .join(' ');
}

function TrainingSummary({ summary }) {
    const metrics = [
        ['Всего обучено', summary.total],
        ['Из них мужчин', summary.men],
        ['Из них женщин', summary.women],
        ...(summary.sex_not_specified
            ? [['Пол не указан', summary.sex_not_specified]]
            : []),
    ];
    return (
        <section
            className={styles.panel}
            aria-labelledby="training-summary-title"
        >
            <h2 id="training-summary-title">Общее количество обучений</h2>
            <p className={styles.meta}>
                Каждое завершение модуля считается отдельным обучением. Один
                слушатель может быть учтён несколько раз.
            </p>
            <dl className={styles.metrics}>
                {metrics.map(([label, count]) => (
                    <div key={label} className={styles.metric}>
                        <dt>{label}</dt>
                        <dd>{number.format(count)}</dd>
                    </div>
                ))}
            </dl>
            <p className={styles.meta}>
                В том числе в архивных группах:{' '}
                <strong>{number.format(summary.archived)}</strong>. Активность
                учётной записи слушателя не влияет на учёт завершённого
                обучения.
            </p>
        </section>
    );
}
function ModuleBreakdown({ directions }) {
    return (
        <section
            className={styles.panel}
            aria-labelledby="module-statistics-title"
        >
            <h2 id="module-statistics-title">
                Обучение по модулям и специальностям
            </h2>
            <p className={styles.meta}>
                Специальность определяется направлением программы:
                бортпроводники, пилоты, инженеры или представители.
            </p>
            {directions.map((direction) => (
                <section
                    key={direction.code}
                    className={styles.direction}
                    aria-label={direction.title}
                >
                    <div className={styles.directionHeader}>
                        <h3>{direction.title}</h3>
                        <p>Обучений: {number.format(direction.total)}</p>
                    </div>
                    {direction.modules.length ? (
                        <div className={styles.tableWrap}>
                            <table
                                className={styles.table}
                                aria-label={`Модули: ${direction.title}`}
                            >
                                <thead>
                                    <tr>
                                        <th scope="col">Код модуля</th>
                                        <th scope="col" className={styles.moduleTitle}>Название модуля</th>
                                        <th
                                            scope="col"
                                            className={styles.number}
                                        >
                                            Обучено
                                        </th>
                                        {fundingColumns.map(([code, title]) => (
                                            <th
                                                scope="col"
                                                className={styles.number}
                                                key={code}
                                            >
                                                {title}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {direction.modules.map((module) => (
                                        <tr key={module.id}>
                                            <td className={styles.code} title={module.title}>
                                                {module.code || '—'}
                                            </td>
                                            <th scope="row" className={styles.moduleTitle}>{module.title}</th>
                                            <td className={styles.number}>
                                                {number.format(module.total)}
                                            </td>
                                            {fundingColumns.map(([code]) => (
                                                <td
                                                    className={styles.number}
                                                    key={code}
                                                >
                                                    {number.format(
                                                        module[code],
                                                    )}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                                <tfoot>
                                    <tr>
                                        <th colSpan={2} scope="row" className={styles.fullTotal}>
                                            Итого по направлению
                                        </th>
                                        <th scope="row" className={styles.compactTotal}>Итого по направлению</th>
                                        <td className={styles.number}>
                                            <strong>
                                                {number.format(direction.total)}
                                            </strong>
                                        </td>
                                        {fundingColumns.map(([code]) => (
                                            <td
                                                className={styles.number}
                                                key={code}
                                            >
                                                <strong>
                                                    {number.format(
                                                        direction[code],
                                                    )}
                                                </strong>
                                            </td>
                                        ))}
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    ) : (
                        <p className={styles.meta}>
                            За выбранный период завершённых обучений нет.
                        </p>
                    )}
                </section>
            ))}
        </section>
    );
}
function FinancingOverview({ data }) {
    const sources = [...data.by_source].sort(
        (a, b) => (a.code === 'unspecified') - (b.code === 'unspecified'),
    );
    return (
        <section
            className={styles.panel}
            aria-labelledby="funding-statistics-title"
        >
            <h2 id="funding-statistics-title">
                Источники финансирования обучения
            </h2>
            <p className={styles.meta}>
                Количество завершённых обучений за выбранный период. Источник
                задаётся у каждого назначения слушателя на модуль.
            </p>
            <dl className={styles.metrics}>
                {sources.map((row) => (
                    <div className={styles.metric} key={row.code}>
                        <dt>{row.title}</dt>
                        <dd>{number.format(row.total)}</dd>
                    </div>
                ))}
            </dl>
            {data.by_source.some(
                (row) => row.code === 'unspecified' && row.total > 0,
            ) && (
                <p className={styles.notice}>
                    Для части обучений источник финансирования ещё не заполнен.
                    Они входят в общий итог и показаны в колонке «Не указано».
                </p>
            )}
            <h3>Компании-плательщики</h3>
            {data.companies.length ? (
                <div className={styles.tableWrap}>
                    <table
                        className={styles.table}
                        aria-label="Обучения по компаниям-плательщикам"
                    >
                        <thead>
                            <tr>
                                <th scope="col">Компания</th>
                                <th scope="col" className={styles.number}>
                                    Всего
                                </th>
                                <th scope="col" className={styles.number}>
                                    За счёт НордСтар
                                </th>
                                <th scope="col" className={styles.number}>
                                    Внешний заказчик
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.companies.map((row) => (
                                <tr key={row.id ?? 'missing'}>
                                    <th scope="row">{row.name}</th>
                                    <td className={styles.number}>
                                        {number.format(row.total)}
                                    </td>
                                    <td className={styles.number}>
                                        {number.format(row.company_internal)}
                                    </td>
                                    <td className={styles.number}>
                                        {number.format(row.company_external)}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            ) : (
                <p className={styles.meta}>
                    За выбранный период обучений с указанным финансированием
                    юрлицами нет.
                </p>
            )}
        </section>
    );
}

function DataQuality({ result }) {
    const missing = result.data_quality.completed_without_date;
    const unclassified = result.data_quality.unclassified_in_period;
    const fallback = result.summary.used_group_date;
    if (!missing && !unclassified && !fallback) return null;
    return (
        <aside
            className={styles.notice}
            aria-label="Сведения о датах и полноте данных"
        >
            {fallback > 0 && (
                <p>
                    Для {number.format(fallback)} обучений без индивидуальной
                    даты использована фактическая дата завершения группы.
                </p>
            )}
            {missing > 0 && (
                <p>
                    В базе есть завершённые обучения без индивидуальной даты и
                    фактической даты завершения группы: {number.format(missing)}
                    . Их нельзя отнести к периоду, поэтому они не включены в
                    расчёт. Проверьте даты в этих записях.
                </p>
            )}
            {unclassified > 0 && (
                <p>
                    У {number.format(unclassified)} обучений за выбранный период
                    не распознано направление программы. Они включены в общий
                    итог и показаны отдельно в разбивке.
                </p>
            )}
        </aside>
    );
}

export default function AUCStatistics() {
    const [dateFrom, setDateFrom] = useState('');
    const [fundingSource, setFundingSource] = useState('all');
    const [payer, setPayer] = useState('');
    const [references, setReferences] = useState(null);
    const [dateTo, setDateTo] = useState('');
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const request = useRef(null);
    useEffect(() => () => request.current?.abort(), []);
    useEffect(() => {
        const controller = new AbortController();
        api.get('/api/execution/director/statistics/auc/filters/', {
            signal: controller.signal,
        })
            .then(({ data }) => setReferences(data))
            .catch((err) => {
                if (!controller.signal.aborted) setError(errorText(err));
            });
        return () => controller.abort();
    }, []);
    async function submit(event) {
        event.preventDefault();
        if (loading) return;
        if (dateFrom > dateTo) {
            setError('Дата начала периода не может быть позже даты окончания.');
            return;
        }
        request.current?.abort();
        const controller = new AbortController();
        request.current = controller;
        setLoading(true);
        setError('');
        setResult(null);
        try {
            const { data } = await api.get(
                '/api/execution/director/statistics/auc/',
                {
                    params: {
                        date_from: dateFrom,
                        date_to: dateTo,
                        funding_source: fundingSource,
                        ...(payer ? { payer_organization: payer } : {}),
                    },
                    signal: controller.signal,
                },
            );
            if (!controller.signal.aborted) setResult(data);
        } catch (err) {
            if (!controller.signal.aborted) setError(errorText(err));
        } finally {
            if (!controller.signal.aborted) setLoading(false);
        }
    }
    return (
        <div className={styles.page}>
            <h1>Статистика АУЦ</h1>
            <p className={styles.meta}>
                Для внутреннего использования. Сводные данные по всему АУЦ,
                включая архивные группы.
            </p>
            <form className={styles.filters} onSubmit={submit}>
                <label>
                    Дата начала
                    <input
                        className={styles.field}
                        type="date"
                        required
                        value={dateFrom}
                        disabled={loading}
                        onChange={(e) => setDateFrom(e.target.value)}
                    />
                </label>
                <label>
                    Дата окончания
                    <input
                        className={styles.field}
                        type="date"
                        required
                        min={dateFrom || undefined}
                        value={dateTo}
                        disabled={loading}
                        onChange={(e) => setDateTo(e.target.value)}
                    />
                </label>
                {references && (
                    <>
                        <label>
                            Источник финансирования
                            <select
                                className={styles.field}
                                disabled={loading}
                                value={fundingSource}
                                onChange={(e) => {
                                    setFundingSource(e.target.value);
                                    if (
                                        ['self_paid', 'unspecified'].includes(
                                            e.target.value,
                                        )
                                    )
                                        setPayer('');
                                }}
                            >
                                <option value="all">Все источники</option>
                                {references.funding_choices.map((row) => (
                                    <option key={row.code} value={row.code}>
                                        {row.title}
                                    </option>
                                ))}
                            </select>
                        </label>
                        <label>
                            Компания-плательщик
                            <select
                                className={styles.field}
                                disabled={
                                    loading ||
                                    ['self_paid', 'unspecified'].includes(
                                        fundingSource,
                                    )
                                }
                                value={payer}
                                onChange={(e) => setPayer(e.target.value)}
                            >
                                <option value="">Все компании</option>
                                {references.organizations.map((row) => (
                                    <option key={row.id} value={row.id}>
                                        {row.company_name}
                                        {!row.is_active && ' (неактивна)'}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </>
                )}
                <button
                    className={styles.primary}
                    disabled={loading || !references}
                >
                    {loading ? 'Расчёт…' : 'Сформировать статистику'}
                </button>
            </form>
            <p className={styles.meta}>
                Обе даты включаются в период. Отбор выполняется по фактической
                дате завершения обучения; если индивидуальная дата не заполнена
                — по фактической дате завершения группы.
            </p>
            {error && (
                <p role="alert" className={styles.error}>
                    {error}
                </p>
            )}
            {loading && <p role="status">Формирование статистики…</p>}
            {!result && !loading && !error && (
                <p className={styles.notice}>
                    Укажите период и нажмите «Сформировать статистику».
                </p>
            )}
            {result &&
                !loading &&
                (dateFrom !== result.period.date_from ||
                    dateTo !== result.period.date_to ||
                    fundingSource !== result.filters.funding_source ||
                    payer !==
                        String(result.filters.payer_organization || '')) && (
                    <p className={styles.notice}>
                        Параметры изменены. Нажмите «Сформировать статистику»,
                        чтобы пересчитать показатели за новый период.
                    </p>
                )}
            {result && !loading && (
                <>
                    <p className={styles.period}>
                        Период: {dateLabel(result.period.date_from)} —{' '}
                        {dateLabel(result.period.date_to)}
                    </p>
                    <p className={styles.meta}>
                        Источник:{' '}
                        {result.filters.funding_source === 'all'
                            ? 'все источники'
                            : references?.funding_choices.find(
                                  (row) =>
                                      row.code ===
                                      result.filters.funding_source,
                              )?.title}
                        . Плательщик:{' '}
                        {result.filters.payer_name || 'все компании'}.
                    </p>
                    <DataQuality result={result} />
                    {result.summary.total === 0 && (
                        <p className={styles.notice}>
                            За выбранный период завершённых обучений не найдено.
                        </p>
                    )}
                    <TrainingSummary summary={result.summary} />
                    <ModuleBreakdown directions={result.by_direction} />
                    <FinancingOverview data={result.funding} />
                </>
            )}
        </div>
    );
}
