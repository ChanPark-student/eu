import { Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';

function MainLayout() {
    return (
        <div className="min-h-screen flex flex-col w-full bg-slate-50 dark:bg-slate-950 font-sans transition-colors duration-300">
            <Header />
            <main className="flex-grow w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in relative z-10">
                {/* Decorative background blobs for PRO MAX feel */}
                <div className="absolute top-0 -left-4 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-2xl opacity-30 animate-pulse-subtle -z-10 dark:bg-purple-900 pointer-events-none"></div>
                <div className="absolute top-0 -right-4 w-72 h-72 bg-blue-300 rounded-full mix-blend-multiply filter blur-2xl opacity-30 animate-pulse-subtle -z-10 animation-delay-2000 dark:bg-blue-900 pointer-events-none"></div>

                <Outlet />
            </main>
            <Footer />
        </div>
    );
}

export default MainLayout;
