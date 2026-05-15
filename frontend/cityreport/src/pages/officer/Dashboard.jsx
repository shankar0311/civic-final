import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, CheckCircle, AlertCircle, Filter } from 'lucide-react';
import Navbar from '../../components/shared/Navbar';
import Card from '../../components/shared/Card';
import Badge from '../../components/shared/Badge';
import Button from '../../components/shared/Button';
import api from '../../api';
import './OfficerDashboard.css';

const OfficerDashboard = () => {
    const navigate = useNavigate();
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const [priorityFilter, setPriorityFilter] = useState('');

    useEffect(() => {
        fetchReports();
    }, [filter, priorityFilter]);

    const fetchReports = async () => {
        try {
            setLoading(true);
            const params = {
                sort_by: 'priority',
                sort_order: 'desc',
                category: 'road_issues'
            };

            if (filter !== 'all') {
                params.status = filter;
            }
            if (priorityFilter) {
                params.priority = priorityFilter;
            }

            const response = await api.get('/reports/', { params });
            setReports(Array.isArray(response.data) ? response.data : response.data.items || []);
        } catch (err) {
            console.error('Error fetching reports:', err);
        } finally {
            setLoading(false);
        }
    };

    const updateStatus = async (id, newStatus) => {
        try {
            const { data } = await api.patch(`/reports/${id}/status`, null, { params: { new_status: newStatus } });
            setReports(prev => prev.map(r => r.id === id ? { ...r, status: data.status } : r));
        } catch (err) {
            console.error('Status update failed:', err);
            alert('Failed to update status.');
        }
    };

    const stats = {
        pending: reports.filter(r => r.status === 'pending').length,
        inProgress: reports.filter(r => r.status === 'in_progress').length,
        resolved: reports.filter(r => r.status === 'resolved' || r.status === 'closed').length,
        reopened: reports.filter(r => r.status === 'reopened').length
    };

    const getStatusVariant = (status) => {
        switch (status.toLowerCase()) {
            case 'resolved':
            case 'closed':
                return 'success';
            case 'in_progress':
            case 'assigned':
                return 'warning';
            case 'pending':
                return 'danger';
            case 'reopened':
                return 'danger';
            default:
                return 'neutral';
        }
    };

    const getPriorityVariant = (priority) => {
        switch (priority.toLowerCase()) {
            case 'high':
                return 'danger';
            case 'medium':
                return 'warning';
            case 'low':
                return 'info';
            default:
                return 'neutral';
        }
    };

    return (
      <div className="min-h-screen bg-background">
        <Navbar />

        <main className="container py-lg">
          <div className="dashboard-header">
            <div>
              <h1 className="text-2xl mb-xs">Officer Dashboard</h1>
              <p className="text-muted">
                Manage road-repair reports and update their status
              </p>
            </div>
          </div>

          <div className="stats-grid">
            <Card className="stat-card">
              <div className="stat-icon pending">
                <Clock size={24} />
              </div>
              <div className="stat-content">
                <p className="stat-label">Pending</p>
                <p className="stat-value">{stats.pending}</p>
              </div>
            </Card>

            <Card className="stat-card">
              <div className="stat-icon in-progress">
                <AlertCircle size={24} />
              </div>
              <div className="stat-content">
                <p className="stat-label">In Progress</p>
                <p className="stat-value">{stats.inProgress}</p>
              </div>
            </Card>

            <Card className="stat-card">
              <div className="stat-icon resolved">
                <CheckCircle size={24} />
              </div>
              <div className="stat-content">
                <p className="stat-label">Resolved</p>
                <p className="stat-value">{stats.resolved}</p>
              </div>
            </Card>

            <Card className="stat-card">
              <div className="stat-icon pending" style={{ background: 'var(--danger-light, #fee2e2)' }}>
                <AlertCircle size={24} style={{ color: 'var(--danger)' }} />
              </div>
              <div className="stat-content">
                <p className="stat-label">Disputed</p>
                <p className="stat-value" style={{ color: stats.reopened > 0 ? 'var(--danger)' : undefined }}>
                  {stats.reopened}
                </p>
              </div>
            </Card>
          </div>

          {/* Filter Panel */}
          <Card className="mt-lg mb-md" style={{ padding: "1.5rem" }}>
            <div className="flex items-center gap-sm mb-md">
              <Filter size={20} />
              <h3 className="font-semibold">Filters</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
              <div>
                <label className="block text-sm font-medium mb-xs">
                  Priority
                </label>
                <select
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "0.5rem",
                    border: "1px solid var(--border)",
                    borderRadius: "0.375rem",
                  }}
                >
                  <option value="">All Priorities</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>
          </Card>

          <Card className="mt-lg">
            <div className="flex justify-between items-center mb-md flex-wrap gap-md">
              <h2 className="text-xl">Assigned Reports</h2>
              <div className="filter-tabs">
                <button
                  className={`filter-tab ${filter === "all" ? "active" : ""}`}
                  onClick={() => setFilter("all")}
                >
                  All
                </button>
                <button
                  className={`filter-tab ${filter === "pending" ? "active" : ""}`}
                  onClick={() => setFilter("pending")}
                >
                  Pending
                </button>
                <button
                  className={`filter-tab ${filter === "in_progress" ? "active" : ""}`}
                  onClick={() => setFilter("in_progress")}
                >
                  In Progress
                </button>
                <button
                  className={`filter-tab ${filter === "reopened" ? "active" : ""}`}
                  onClick={() => setFilter("reopened")}
                  style={stats.reopened > 0 ? { color: 'var(--danger)', fontWeight: 600 } : {}}
                >
                  Disputed {stats.reopened > 0 && `(${stats.reopened})`}
                </button>
              </div>
            </div>

            {loading ? (
              <div className="text-center py-lg">
                <p>Loading reports...</p>
              </div>
            ) : (
              <div className="reports-table-container">
                <table className="reports-table">
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Priority</th>
                      <th>Status</th>
                      <th>Created Date</th>
                      <th>Upvotes</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((report) => (
                      <tr key={report.id}>
                        <td>
                          <span className="font-semibold">{report.title}</span>
                          {report.status === 'reopened' && report.citizen_feedback && (
                            <p className="text-xs text-danger mt-xs" style={{ maxWidth: 240 }}>
                              Dispute: "{report.citizen_feedback}"
                            </p>
                          )}
                        </td>
                        <td>
                          <Badge variant={getPriorityVariant(report.priority)}>
                            {report.priority}
                          </Badge>
                        </td>
                        <td>
                          <Badge variant={getStatusVariant(report.status)}>
                            {report.status}
                          </Badge>
                        </td>
                        <td>
                          {new Date(report.created_at).toLocaleDateString()}
                        </td>
                        <td>{report.upvotes}</td>
                        <td>
                          <div className="flex gap-xs flex-wrap">
                            {report.status === 'pending' && (
                              <Button size="sm" variant="warning"
                                onClick={() => updateStatus(report.id, 'in_progress')}>
                                Start
                              </Button>
                            )}
                            {report.status === 'reopened' && (
                              <Button size="sm" variant="warning"
                                onClick={() => updateStatus(report.id, 'in_progress')}>
                                Investigate
                              </Button>
                            )}
                            {(report.status === 'pending' || report.status === 'in_progress' || report.status === 'reopened') && (
                              <Button size="sm" variant="success"
                                onClick={() => updateStatus(report.id, 'resolved')}>
                                Resolve
                              </Button>
                            )}
                            {report.status === 'resolved' && (
                              <span className="text-xs text-muted" style={{lineHeight:'2rem'}}>Resolved ✓</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </main>
      </div>
    );
};

export default OfficerDashboard;
