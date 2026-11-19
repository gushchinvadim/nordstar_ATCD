export const emptyFunding = {
    funding_source: 'unspecified',
    payer_organization: null,
    funding_reference: '',
};
export function fundingValue(row) {
    return {
        funding_source: row.funding_source || 'unspecified',
        payer_organization: row.payer_organization || null,
        funding_reference: row.funding_reference || '',
    };
}
