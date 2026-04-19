import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import api from '../../api';
import Navbar from '../../components/shared/Navbar';
import Button from '../../components/shared/Button';
import ReportCard from '../../components/citizen/ReportCard';
import FilterBar from '../../components/shared/FilterBar';
import { useAuth } from '../../contexts/AuthContext';

const SEVERITY_ORDER = { critical: 4, high: 3, medium: 2, low: 1 };

const MyReports = () => {
    const navigate = useNavigate();
    const { user } = useAuth();
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [filters, setFilters] = useState({ status: '' });
    const [sortBy, setSortBy] = useState('newest');

    useEffect(() => {
        api.get('/reports/mine')
            .then(({ data }) => setReports(data))
            .catch(() => setError('Failed to load reports.'))
            .finally(() => setLoading(false));
    }, []);

    const handleWithdraw = async (id) => {
        if (!window.confirm('Are you sure you want to delete this report? This cannot be undone.')) return;
        try {
            await api.delete(`/reports/${id}`);
            setReports(prev => prev.filter(r => r.id !== id));
        } catch (err) {
            const msg = err?.response?.data?.detail || 'Failed to delete report.';
            alert(msg);
        }
    };

    const handleUpvote = async (id) => {
        try {
            await api.post(`/reports/${id}/upvote`);
            const { data } = await api.get('/reports/mine');
            setReports(data);
        } catch {}
    };

    const filtered = useMemo(() => {
        const f = reports.filter(r => {
            const matchSearch =
                r.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                (r.description || '').toLowerCase().includes(searchTerm.toLowerCase());
            const matchStatus = filters.status ? r.status === filters.status : true;
            return matchSearch && matchStatus;
        });

        return [...f].sort((a, b) => {
            if (sortBy === 'upvotes')  return (b.upvotes ?? 0) - (a.upvotes ?? 0);
            if (sortBy === 'newest')   return new Date(b.created_at) - new Date(a.created_at);
            if (sortBy === 'oldest')   return new Date(a.created_at) - new Date(b.created_at);
            if (sortBy === 'severity') return (SEVERITY_ORDER[b.ai_severity_level] ?? 0) - (SEVERITY_ORDER[a.ai_severity_level] ?? 0);
            return 0;
        });
    }, [reports, searchTerm, filters, sortBy]);

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            <main className="container py-lg">
                <div className="flex flex-col md:flex-row justify-between items-center mb-lg gap-md">
                    <div>
                        <h1 className="text-2xl mb-xs">My Reports</h1>
                        <p className="text-muted">All issues you have submitted to the city.</p>
                    </div>
                    <Button variant="primary" size="lg" icon={Plus} onClick={() => navigate('/citizen/report/new')}>
                        Report an Issue
                    </Button>
                </div>

                <FilterBar
                    onSearch={setSearchTerm}
                    onFilterChange={(type, value) => setFilters(prev => ({ ...prev, [type]: value }))}
                    onSortChange={setSortBy}
                />

                {error && (
                    <div style={{ padding: '1rem', marginBottom: '1rem', background: '#fee', color: '#c00', borderRadius: '0.5rem' }}>
                        {error}
                    </div>
                )}

                {loading ? (
                    <p className="text-center text-muted py-lg">Loading reports...</p>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-lg">
                        {filtered.length > 0 ? (
                            filtered.map(report => (
                                <ReportCard
                                    key={report.id}
                                    report={report}
                                    onUpvote={handleUpvote}
                                    onClick={(id) => navigate(`/citizen/report/${id}`)}
                                    onWithdraw={handleWithdraw}
                                    isOwner={true}
                                />
                            ))
                        ) : (
                            <div className="col-span-full text-center py-lg text-muted" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                                {reports.length === 0 ? (
                                    <>
                                        <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <rect x="8" y="16" width="56" height="44" rx="6" fill="#e0e7ff" />
                                            <rect x="18" y="28" width="36" height="5" rx="2.5" fill="#a5b4fc" />
                                            <rect x="18" y="39" width="24" height="5" rx="2.5" fill="#c7d2fe" />
                                            <circle cx="54" cy="18" r="12" fill="#f0fdf4" stroke="#86efac" strokeWidth="2" />
                                            <path d="M49 18l3.5 3.5 7-7" stroke="#22c55e" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                                        </svg>
                                        <div>
                                            <p style={{ fontWeight: 600, fontSize: '1rem' }}>No reports yet.</p>
                                            <p style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>Be the first to report an issue in your area!</p>
                                        </div>
                                        <Button variant="primary" icon={Plus} onClick={() => navigate('/citizen/report/new')}>
                                            Report an Issue
                                        </Button>
                                    </>
                                ) : (
                                    <p>No reports match your search or filter.</p>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
};

export default MyReports;
