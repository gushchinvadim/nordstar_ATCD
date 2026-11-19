import styles from './FundingFields.module.css';
export default function FundingFields({
    value,
    references,
    onChange,
    disabled = false,
}) {
    const corporate = ['company_internal', 'company_external'].includes(
        value.funding_source,
    );
    return (
        <div className={styles.fields}>
            <label>
                Источник финансирования
                <select
                    className={styles.field}
                    disabled={disabled}
                    value={value.funding_source}
                    onChange={(e) =>
                        onChange({
                            ...value,
                            funding_source: e.target.value,
                            payer_organization: [
                                'company_internal',
                                'company_external',
                            ].includes(e.target.value)
                                ? value.payer_organization
                                : null,
                        })
                    }
                >
                    {references.funding_choices.map((row) => (
                        <option key={row.code} value={row.code}>
                            {row.title}
                        </option>
                    ))}
                </select>
            </label>
            {corporate && (
                <label>
                    Компания-плательщик
                    <select
                        className={styles.field}
                        required
                        disabled={disabled}
                        value={value.payer_organization || ''}
                        onChange={(e) =>
                            onChange({
                                ...value,
                                payer_organization: e.target.value
                                    ? Number(e.target.value)
                                    : null,
                            })
                        }
                    >
                        <option value="">Выберите компанию</option>
                        {references.organizations.map((row) => (
                            <option
                                key={row.id}
                                value={row.id}
                                disabled={
                                    !row.is_active &&
                                    row.id !== Number(value.payer_organization)
                                }
                            >
                                {row.company_name}
                                {!row.is_active && ' (неактивна)'}
                            </option>
                        ))}
                    </select>
                </label>
            )}
            <label>
                Договор / заявка (необязательно)
                <input
                    className={styles.field}
                    maxLength={120}
                    disabled={disabled}
                    value={value.funding_reference}
                    onChange={(e) =>
                        onChange({
                            ...value,
                            funding_reference: e.target.value,
                        })
                    }
                />
            </label>
        </div>
    );
}
