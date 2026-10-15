// src/pages/methodist/GroupGrades.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../api/config';
import styles from './GroupGrades.module.css';

const GroupGrades = () => {
    const { groupId } = useParams();
    const navigate = useNavigate();
    
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [groupInfo, setGroupInfo] = useState(null);
    const [instructors, setInstructors] = useState([]);
    const [students, setStudents] = useState([]);
    const [changedCells, setChangedCells] = useState(new Set());

    useEffect(() => {
        fetchData();
    }, [groupId]);

    const fetchData = async () => {
        setLoading(true);
        try {
            const response = await api.get(`/api/docs/groups/${groupId}/grades/`);
            setGroupInfo(response.data.group_info);
            setInstructors(response.data.instructors);
            setStudents(response.data.students);
        } catch (error) {
            console.error("Ошибка загрузки данных:", error);
            alert("Не удалось загрузить журнал оценок");
        } finally {
            setLoading(false);
        }
    };

    const handleCellChange = (enrollmentId, sectionId, field, value) => {
        const key = `${enrollmentId}_${sectionId}_${field}`;
        setChangedCells(prev => new Set(prev).add(key));

        setStudents(prevStudents => prevStudents.map(student => {
            if (student.enrollment_id !== enrollmentId) return student;
            
            return {
                ...student,
                assessments: student.assessments.map(assess => {
                    if (assess.section_id !== sectionId) return assess;
                    return { ...assess, [field]: value };
                })
            };
        }));
    };

    const saveGrades = async () => {
        if (changedCells.size === 0) {
            alert("Нет изменений для сохранения");
            return;
        }

        if (!window.confirm(`Сохранить изменения? Будет обновлено ячеек: ${changedCells.size}`)) {
            return;
        }

        setSaving(true);
        const updates = [];

        students.forEach(student => {
            student.assessments.forEach(assess => {
                const scoreKey = `${student.enrollment_id}_${assess.section_id}_score`;
                const dateKey = `${student.enrollment_id}_${assess.section_id}_date`;
                const instKey = `${student.enrollment_id}_${assess.section_id}_instructor_id`;

                if (changedCells.has(scoreKey) || changedCells.has(dateKey) || changedCells.has(instKey)) {
                    updates.push({
                        enrollment_id: student.enrollment_id,
                        section_id: assess.section_id,
                        score: assess.score,
                        date: assess.date,
                        instructor_id: assess.instructor_id
                    });
                }
            });
        });

        try {
            const response = await api.post(`/api/docs/groups/${groupId}/grades/`, { updates });
            alert(response.data.message || `Сохранено: ${response.data.saved_count}`);
            if (response.data.warnings) {
                alert("Предупреждения:\n" + response.data.warnings.join('\n'));
            }
            setChangedCells(new Set());
            fetchData();
        } catch (error) {
            console.error("Ошибка сохранения:", error);
            alert("Ошибка при сохранении оценок");
        } finally {
            setSaving(false);
        }
    };

    const completeAllPassed = async () => {
        if (!window.confirm('Завершить обучение для всех студентов, сдавших все разделы?')) {
            return;
        }

        try {
            const response = await api.post(`/api/docs/groups/${groupId}/complete-all/`);
            alert(`✅ ${response.data.message}`);
            fetchData();
        } catch (error) {
            console.error("Ошибка:", error);
            alert(error.response?.data?.error || 'Ошибка при завершении группы');
        }
    };

    const dismissFailed = async () => {
        if (!window.confirm('⚠️ Отчислить всех студентов, не сдавших разделы? Это действие необратимо!')) {
            return;
        }

        try {
            const response = await api.post(`/api/docs/groups/${groupId}/dismiss-failed/`);
            alert(`✅ ${response.data.message}`);
            fetchData();
        } catch (error) {
            console.error("Ошибка:", error);
            alert(error.response?.data?.error || 'Ошибка при отчислении');
        }
    };

    if (loading) return <div className={styles.loading}>Загрузка журнала...</div>;
    
    if (!groupInfo) {
        return (
            <div className={styles.container}>
                <div className={styles.error}>
                    <h2>❌ Не удалось загрузить журнал оценок</h2>
                    <button className={styles.backBtn} onClick={() => navigate('/groups')}>← Назад</button>
                </div>
            </div>
        );
    }

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <button className={styles.backBtn} onClick={() => navigate('/groups')}>← Назад к группам</button>
                <h1>Журнал оценок: {groupInfo.assigned_number}</h1>
                <p>{groupInfo.module_code} — {groupInfo.module_title}</p>
            </div>

            {/* ПАНЕЛЬ МАССОВЫХ ДЕЙСТВИЙ */}
            <div className={styles.massActions}>
                <button 
                    className={`${styles.massBtn} ${styles.saveBtn} ${changedCells.size > 0 ? styles.hasChanges : ''}`} 
                    onClick={saveGrades}
                    disabled={saving || changedCells.size === 0}
                >
                     {saving ? 'Сохранение...' : `Сохранить оценки (${changedCells.size})`}
                </button>
                
                <button 
                    className={`${styles.massBtn} ${styles.completeBtn}`} 
                    onClick={completeAllPassed}
                >
                    ✓ Завершить всех сдавших
                </button>
                
                <button 
                    className={`${styles.massBtn} ${styles.dismissBtn}`} 
                    onClick={dismissFailed}
                >
                    ⚠ Отчислить не сдавших
                </button>
            </div>

            <div className={styles.tableWrapper}>
                <table className={styles.gradesTable}>
                    <thead>
                        <tr>
                            <th className={styles.stickyCol1}>№</th>
                            <th className={styles.stickyCol2}>ФИО студента</th>
                            <th className={styles.stickyCol3}>Статус</th>
                            {students.length > 0 && students[0].assessments && students[0].assessments.map(assess => (
                                <th key={assess.section_id} className={styles.sectionHeader} title={assess.section_title}>
                                    {assess.section_title.length > 30 ? assess.section_title.substring(0, 30) + '...' : assess.section_title}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {students.map(student => (
                            <tr key={student.enrollment_id} className={styles[`status${student.status}`]}>
                                <td className={styles.stickyCol1}>{student.number_in_group}</td>
                                <td className={`${styles.stickyCol2} ${styles.studentName}`}>{student.student_name}</td>
                                <td className={styles.stickyCol3}>{student.status_display}</td>
                                
                                {student.assessments && student.assessments.map(assess => {
                                    const isChanged = changedCells.has(`${student.enrollment_id}_${assess.section_id}_score`) ||
                                                      changedCells.has(`${student.enrollment_id}_${assess.section_id}_date`);
                                    
                                    return (
                                        <td key={assess.section_id} className={`${styles.assessmentCell} ${isChanged ? styles.changed : ''}`}>
                                            {assess.grade_type === 'binary' || assess.grade_type === 'pass_fail' ? (
                                                <select 
                                                    value={assess.score ?? ''} 
                                                    onChange={(e) => handleCellChange(student.enrollment_id, assess.section_id, 'score', e.target.value === '' ? null : parseInt(e.target.value))}
                                                    className={styles.inputSelect}
                                                >
                                                    <option value="">—</option>
                                                    <option value="1">✓ Зачтено</option>
                                                    <option value="0">Не зачтено</option>
                                                </select>
                                            ) : (
                                                <input 
                                                    type="number" 
                                                    min="0" max="5" 
                                                    value={assess.score ?? ''} 
                                                    onChange={(e) => handleCellChange(student.enrollment_id, assess.section_id, 'score', e.target.value === '' ? null : parseInt(e.target.value))}
                                                    className={styles.inputNumber}
                                                    placeholder="—"
                                                />
                                            )}
                                            
                                            <input 
                                                type="date" 
                                                value={assess.date || ''} 
                                                onChange={(e) => handleCellChange(student.enrollment_id, assess.section_id, 'date', e.target.value)}
                                                className={styles.inputDate}
                                            />
                                            
                                            <select 
                                                value={assess.instructor_id || ''} 
                                                onChange={(e) => handleCellChange(student.enrollment_id, assess.section_id, 'instructor_id', e.target.value === '' ? null : parseInt(e.target.value))}
                                                className={styles.inputSelectSmall}
                                                title="Преподаватель"
                                            >
                                                <option value="">— преп. —</option>
                                                {instructors.map(inst => (
                                                    <option key={inst.id} value={inst.id}>{inst.name}</option>
                                                ))}
                                            </select>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default GroupGrades;