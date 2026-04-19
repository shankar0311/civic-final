import React from 'react';
import { Link } from 'react-router-dom';
import Button from '../../components/shared/Button';
import Card from '../../components/shared/Card';

const Welcome = () => {
    return (
        <div className="container flex flex-col items-center justify-center h-full" style={{ minHeight: '100vh' }}>
            <div className="text-center mb-md">
                <h1 className="text-2xl" style={{ color: 'var(--primary)', marginBottom: '1rem' }}>Citizen Road Reporting</h1>
                <p className="text-muted">Smart City Urban Issue Reporting Platform</p>
            </div>

            <div className="grid grid-cols-1 gap-md w-full" style={{ maxWidth: '400px' }}>
                <Card className="flex flex-col gap-md items-center">
                    <h2 className="text-xl">Get Started</h2>
                    <div className="flex flex-col gap-sm w-full">
                        <Link to="/login">
                            <Button fullWidth variant="primary">Login</Button>
                        </Link>
                        <Link to="/signup">
                            <Button fullWidth variant="outline">Sign Up</Button>
                        </Link>
                    </div>
                </Card>
            </div>
        </div>
    );
};

export default Welcome;
