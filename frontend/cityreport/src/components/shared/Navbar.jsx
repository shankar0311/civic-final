import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, User, LogOut } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import Button from './Button';
import api from '../../api';
import './Navbar.css';

const Navbar = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const [notifs, setNotifs]       = useState([]);
    const [open, setOpen]           = useState(false);
    const dropdownRef               = useRef(null);

    const unread = notifs.filter(n => !n.is_read).length;

    // Poll every 30s for citizens
    useEffect(() => {
        if (!user || user.role !== 'citizen') return;
        const fetch = () =>
            api.get('/notifications/').then(({ data }) => setNotifs(data)).catch(() => {});
        fetch();
        const id = setInterval(fetch, 30000);
        return () => clearInterval(id);
    }, [user]);

    // Close dropdown on outside click
    useEffect(() => {
        const handler = (e) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const handleBellClick = () => {
        setOpen(o => !o);
        if (!open && unread > 0) {
            api.post('/notifications/read-all').then(() =>
                setNotifs(prev => prev.map(n => ({ ...n, is_read: true })))
            ).catch(() => {});
        }
    };

    const handleNotifClick = (n) => {
        setOpen(false);
        navigate(`/citizen/report/${n.report_id}`);
    };

    const handleLogout = () => { logout(); navigate('/login'); };

    return (
        <nav className="navbar">
            <div className="container navbar-container">
                <div className="navbar-brand">
                    <Link to="/" className="flex items-center gap-sm">
                        <div className="logo-placeholder">C</div>
                        <span className="text-xl font-bold">CityReport</span>
                    </Link>
                </div>

                <div className="navbar-menu hidden md:flex">
                    {user?.role === 'citizen' && (
                        <>
                            <Link to="/citizen/dashboard" className="nav-link">Dashboard</Link>
                            <Link to="/citizen/map" className="nav-link">Map View</Link>
                            <Link to="/citizen/reports" className="nav-link">My Reports</Link>
                        </>
                    )}
                </div>

                <div className="navbar-actions flex items-center gap-md">
                    {/* Bell — only for citizens */}
                    {user?.role === 'citizen' && (
                        <div className="notif-wrapper" ref={dropdownRef}>
                            <button className="icon-btn notif-bell" onClick={handleBellClick}>
                                <Bell size={20} />
                                {unread > 0 && (
                                    <span className="notif-badge">{unread > 9 ? '9+' : unread}</span>
                                )}
                            </button>

                            {open && (
                                <div className="notif-dropdown">
                                    <div className="notif-header">
                                        <span className="notif-title">Notifications</span>
                                        {unread === 0 && notifs.length > 0 && (
                                            <span className="notif-all-read">All caught up</span>
                                        )}
                                    </div>

                                    {notifs.length === 0 ? (
                                        <p className="notif-empty">No notifications yet.</p>
                                    ) : (
                                        <ul className="notif-list">
                                            {notifs.map(n => (
                                                <li
                                                    key={n.id}
                                                    className={`notif-item ${!n.is_read ? 'unread' : ''}`}
                                                    onClick={() => handleNotifClick(n)}
                                                >
                                                    <span className="notif-dot" />
                                                    <div className="notif-body">
                                                        <p className="notif-msg">{n.message}</p>
                                                        <p className="notif-time">
                                                            {new Date(n.created_at).toLocaleString()}
                                                        </p>
                                                    </div>
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    <div className="user-menu flex items-center gap-sm">
                        <div className="avatar"><User size={18} /></div>
                        <span className="hidden md:block text-sm font-medium">{user?.name || 'User'}</span>
                        <Button variant="ghost" size="sm" onClick={handleLogout} className="icon-btn">
                            <LogOut size={18} />
                        </Button>
                    </div>
                </div>
            </div>
        </nav>
    );
};

export default Navbar;
