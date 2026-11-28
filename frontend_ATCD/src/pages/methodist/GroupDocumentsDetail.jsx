// src/pages/methodist/GroupDocumentsDetail.jsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../api/config';
import styles from './GroupDocumentsDetail.module.css';

const GroupDocumentsDetail = () => {
    const { groupId } = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(null); 

    const [downloadingArchive, setDownloadingArchive] = useState(false);

    useEffect(() => {
        loadData();
    }, [groupId]);

    const loadData = async () => {
        setLoading(true);
        try {
            const res = await api.get(`/api/docs/groups/${groupId}/documents/`);
            setData(res.data);
        } catch (err) {
            console.error('Ошибка загрузки документов:', err);
            alert('Не удалось загрузить документы группы');
        } finally {
            setLoading(false);
        }
    };

    const handleViewPdf = async (docKey) => {
        try {
            const response = await api.get(`/api/docs/groups/${groupId}/view-pdf/${docKey}/`, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            window.open(url, '_blank');
        } catch (err) {
            alert(err.response?.data?.error || 'Ошибка сети при открытии документа');
        }
    };

    const handleDownloadPdf = async (docKey) => {
        try {
            const response = await api.get(`/api/docs/groups/${groupId}/download-pdf/${docKey}/`, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `${docKey}.pdf`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            alert(err.response?.data?.error || 'Ошибка сети при скачивании документа');
        }
    };

    const handleDownloadArchive = async () => {
        setDownloadingArchive(true);
        try {
            const response = await api.get(`/api/docs/groups/${groupId}/download-folder/`, { responseType: 'blob' });
            if (response.data.type !== 'application/zip') {
                throw new Error('Ожидался ZIP-архив');
            }
            const disposition = response.headers['content-disposition'] || '';
            const filename = disposition.match(/filename="?([a-zA-Z0-9_]+\.zip)"?/i)?.[1];
            const url = window.URL.createObjectURL(response.data);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename || `group_${groupId}.zip`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
        } catch (err) {
            const status = err.response?.status;
            if (status === 404) {
                alert('У группы пока нет сохранённых документов.');
            } else if (status === 403) {
                alert('У вас нет доступа к архиву этой группы.');
            } else {
                alert('Не удалось скачать архив документов.');
            }
        } finally {
            setDownloadingArchive(false);
        }
    };

    const handleSaveDoc = async (docKey) => {
        if (!window.confirm('Сгенерировать и сохранить этот документ?')) return;
        setActionLoading(docKey);
        try {
            const res = await api.post(`/api/docs/groups/${groupId}/save-document/`, { document_type: docKey });
            if (res.data.success) {
                setData(prevData => ({
                    ...prevData,
                    documents: prevData.documents.map(doc => 
                        doc.key === docKey ? { ...doc, is_saved: true, saved_file_path: res.data.pdf_path } : doc
                    )
                }));
            } else {
                alert(`❌ Ошибка: ${res.data.error}`);
            }
        } catch (err) {
            alert('Ошибка сети при сохранении документа');
        } finally {
            setActionLoading(null);
        }
    };

    const handleSaveAllDocs = async () => {
        if (!window.confirm('Сгенерировать и сохранить ВСЕ доступные PDF-документы для этой группы?')) return;
        setActionLoading('all');
        try {
            const res = await api.post(`/api/docs/groups/${groupId}/generate-all/`);
            if (res.data.success) {
                let msg = `✅ ${res.data.message}`;
                if (res.data.details?.errors?.length > 0) msg += `\n\nОшибки:\n- ${res.data.details.errors.join('\n- ')}`;
                alert(msg);
                await loadData();
            } else {
                alert(`❌ Ошибка: ${res.data.error}`);
            }
        } catch (err) {
            alert('Ошибка сети при массовом сохранении');
        } finally {
            setActionLoading(null);
        }
    };

    const handleSaveReport = async (type, format = null) => {
        const reportName = type === 'rauc' ? `РАУЦ (${format})` : 'ФРДО';
        if (!window.confirm(`Сгенерировать и сохранить отчет ${reportName}?`)) return;
        setActionLoading(`${type}-${format || 'excel'}`);
        try {
            let url = `/api/docs/groups/${groupId}/save-frdo/`;
            if (type === 'rauc') url = `/api/docs/groups/${groupId}/save-rauc/${format}/`;
            const res = await api.post(url);
            if (res.data.success) {
                alert(`✅ ${res.data.message}`);
                setData(prevData => {
                    const newReports = { ...prevData.reports };
                    const filePath = res.data.file_path;
                    if (type === 'rauc' && format === 'excel') newReports.rauc_excel = { saved: true, path: filePath };
                    else if (type === 'rauc' && format === 'xml') newReports.rauc_xml = { saved: true, path: filePath };
                    else if (type === 'frdo') newReports.frdo_excel = { saved: true, path: filePath };
                    return { ...prevData, reports: newReports };
                });
            } else {
                alert(`❌ Ошибка: ${res.data.error}`);
            }
        } catch (err) {
            alert(err.response?.data?.error || 'Ошибка сети при сохранении отчета');
        } finally {
            setActionLoading(null);
        }
    };

    const handleDownloadReport = async (type, format = null) => {
        try {
            let downloadUrl = type === 'rauc' ? `/api/docs/groups/${groupId}/download-rauc/${format}/` : `/api/docs/groups/${groupId}/download-frdo/`;
            const response = await api.get(downloadUrl, { responseType: 'blob' });
            let filename = '';
            const disposition = response.headers['content-disposition'];
            if (disposition && disposition.includes('filename=')) {
                const match = disposition.match(/filename="?([^";]+)"?/);
                if (match) filename = match[1];
            }
            if (!filename) {
                if (type === 'rauc' && format === 'excel') filename = 'РАУЦ.xlsx';
                else if (type === 'rauc' && format === 'xml') filename = 'РАУЦ.xml';
                else if (type === 'frdo') filename = 'ФРДО.xlsx';
            }
            const blob = new Blob([response.data]);
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            alert('Ошибка сети при скачивании отчёта');
        }
    };

    if (loading) return <div className={styles.loading}>Загрузка документов...</div>;
    if (!data) return <div className={styles.error}>Данные не найдены</div>;

    const { group, documents, reports } = data;

    return (
        <div className={styles.container}>
            <button className={styles.backBtn} onClick={() => navigate('/groups')}>
                ← Назад к списку групп
            </button>

            <div className={styles.header}>
                <h1>📁 Документы группы: {group.assigned_number}</h1>
                <div className={styles.meta}>
                    <span className={styles.badge}>{group.module_code}</span>
                    <span>{group.module_title}</span>
                    <span>📅 {group.start_date} — {group.end_date}</span>
                </div>
                
                <div className={styles.actions}>
                    {/* 🔥 КНОПКА РЕДАКТИРОВАНИЯ ГРУППЫ */}
                    <button 
                        className={styles.btnSecondary} 
                        onClick={() => navigate(`/groups/${groupId}/edit`)}
                        title="Исправить данные группы, состав или список слушателей"
                    >
                        ✏️ Редактировать группу
                    </button>

                    {/* 🔥 НОВАЯ КНОПКА: БЫСТРЫЙ ПЕРЕХОД В ЖУРНАЛ ОЦЕНОК */}
                    <button 
                        className={styles.btnSecondary} 
                        onClick={() => navigate(`/groups/${groupId}/grades`)}
                        title="Открыть журнал оценок для выставления и просмотра оценок"
                    >
                        📖 Журнал оценок
                    </button>

                    <button 
                        className={styles.btnPrimary} 
                        onClick={handleSaveAllDocs}
                        disabled={actionLoading === 'all'}
                    >
                        {actionLoading === 'all' ? '⏳ Генерация...' : '📄 Сгенерировать все PDF'}
                    </button>
                    
                    <button
                        type="button"
                        className={styles.btnSecondary}
                        onClick={handleDownloadArchive}
                        disabled={downloadingArchive}
                    >
                        {downloadingArchive ? 'Подготовка архива…' : '📦 Скачать ZIP'}
                    </button>
                </div>
            </div>

            <h2 className={styles.sectionTitle}>📑 Основные документы</h2>
            <div className={styles.grid}>
                {documents.map(doc => (
                    <div key={doc.key} className={styles.card}>
                        <div className={styles.cardHeader}>
                            <span className={styles.icon}>{doc.icon}</span>
                            <h3 className={styles.docName}>{doc.name}</h3>
                        </div>
                        <div className={styles.cardBody}>
                            <div className={`${styles.status} ${doc.is_saved ? styles.statusSaved : styles.statusMissing}`}>
                                {doc.is_saved ? 'Сформирован' : (doc.status === 'coming_soon' ? 'В разработке' : 'Ожидает формирования')}
                            </div>
                        </div>
                        <div className={styles.cardActions}>
                            {doc.status !== 'coming_soon' && (
                                <>
                                    {doc.is_saved ? (
                                        <>
                                            <button className={styles.btnView} onClick={() => handleViewPdf(doc.key)} title="Открыть в браузере">👁 Просмотр</button>
                                            <button className={styles.btnDownload} onClick={() => handleDownloadPdf(doc.key)} title="Скачать PDF">⬇ Скачать PDF</button>
                                        </>
                                    ) : (
                                        <button className={styles.btnGenerate} onClick={() => handleSaveDoc(doc.key)} disabled={actionLoading === doc.key}>
                                            {actionLoading === doc.key ? '⏳...' : '💾 Сгенерировать'}
                                        </button>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <section>
                <h2 className={styles.sectionTitle}>📊 Отчеты для выгрузки</h2>
                <div className={styles.reportsGrid}>
                    <div className={styles.reportCard}>
                        <h4>📗 РАУЦ (Excel)</h4>
                        {reports.rauc_excel?.saved ? (
                            <button className={styles.btnDownload} onClick={() => handleDownloadReport('rauc', 'excel')}>⬇ Скачать</button>
                        ) : (
                            <button className={styles.btnGenerate} onClick={() => handleSaveReport('rauc', 'excel')} disabled={actionLoading === 'rauc-excel'}>
                                {actionLoading === 'rauc-excel' ? '⏳...' : '💾 Сгенерировать'}
                            </button>
                        )}
                    </div>
                    <div className={styles.reportCard}>
                        <h4>📄 РАУЦ (XML)</h4>
                        {reports.rauc_xml?.saved ? (
                            <button className={styles.btnDownload} onClick={() => handleDownloadReport('rauc', 'xml')}>⬇ Скачать</button>
                        ) : (
                            <button className={styles.btnGenerate} onClick={() => handleSaveReport('rauc', 'xml')} disabled={actionLoading === 'rauc-xml'}>
                                {actionLoading === 'rauc-xml' ? '⏳...' : '💾 Сгенерировать'}
                            </button>
                        )}
                    </div>
                    <div className={styles.reportCard}>
                        <h4>📘 ФРДО (Excel)</h4>
                        {reports.frdo_excel?.saved ? (
                            <button className={styles.btnDownload} onClick={() => handleDownloadReport('frdo')}>⬇ Скачать</button>
                        ) : (
                            <button className={styles.btnGenerate} onClick={() => handleSaveReport('frdo')} disabled={actionLoading === 'frdo-excel'}>
                                {actionLoading === 'frdo-excel' ? '⏳...' : '💾 Сгенерировать'}
                            </button>
                        )}
                    </div>
                </div>
            </section>
        </div>
    );
};

export default GroupDocumentsDetail;