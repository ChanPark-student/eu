import { ArrowRight, CheckCircle, Search, ShieldAlert, Cpu } from 'lucide-react';
import { Link } from 'react-router-dom';

function Home() {
    return (
        <div className="space-y-24 pb-16">
            {/* Hero Section */}
            <section className="relative text-center pt-20 pb-16">
                <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8">
                    당신의 AI, <br className="md:hidden" />
                    <span className="gradient-text pb-2">안전합니까?</span>
                </h1>
                <p className="text-xl md:text-2xl text-slate-600 dark:text-slate-300 max-w-3xl mx-auto mb-12 leading-relaxed">
                    EU AI Act 규제 위배 여부를 <span className="font-semibold text-blue-600 dark:text-blue-400">자동으로 검증</span>하고,
                    글로벌 진출을 위한 <span className="font-semibold text-blue-600 dark:text-blue-400">명확한 솔루션</span>을 제공받으세요.
                </p>
                <div className="flex flex-col sm:flex-row justify-center items-center space-y-4 sm:space-y-0 sm:space-x-6">
                    <Link to="/verify" className="w-full sm:w-auto px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-lg transition-all hover-glow flex justify-center items-center space-x-2">
                        <span>지금 바로 검증하기</span>
                        <ArrowRight className="h-5 w-5" />
                    </Link>
                    <button className="w-full sm:w-auto px-8 py-4 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-xl font-bold text-lg transition-colors">
                        서비스 소개서 보기
                    </button>
                </div>
            </section>

            {/* Features Grid */}
            <section className="grid grid-cols-1 md:grid-cols-3 gap-8 px-4">
                {[
                    {
                        icon: <Search className="h-8 w-8 text-blue-500" />,
                        title: "빠른 스코어 점검",
                        desc: "제품 및 기술 수출 시 EU AI Act 규제에 걸릴 위험도를 즉각 계산합니다."
                    },
                    {
                        icon: <ShieldAlert className="h-8 w-8 text-rose-500" />,
                        title: "자동 첨삭 솔루션",
                        desc: "위험 요소가 감지되면, 규제를 통과할 수 있도록 구체적인 보안/수정 가이드를 제공합니다."
                    },
                    {
                        icon: <Cpu className="h-8 w-8 text-indigo-500" />,
                        title: "RAG 기반 심층 분석",
                        desc: "향후 도입될 AI 모듈을 통해 방대한 사내 문서를 기반으로 한 정밀 진단을 지원합니다."
                    }
                ].map((feature, idx) => (
                    <div key={idx} className="glass p-8 rounded-2xl hover:-translate-y-2 transition-transform duration-300 group">
                        <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl w-fit mb-6 group-hover:scale-110 transition-transform">
                            {feature.icon}
                        </div>
                        <h3 className="text-xl font-bold mb-3">{feature.title}</h3>
                        <p className="text-slate-600 dark:text-slate-400">{feature.desc}</p>
                    </div>
                ))}
            </section>

            {/* Trust Section */}
            <section className="bg-blue-600 rounded-3xl p-8 md:p-16 text-center text-white mt-24 shadow-2xl relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-full bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
                <h2 className="text-3xl md:text-4xl font-bold mb-6 relative z-10">
                    복잡한 글로벌 규제, 더 이상 고민하지 마세요.
                </h2>
                <p className="text-blue-100 text-lg md:text-xl max-w-2xl mx-auto mb-10 relative z-10">
                    설문 몇 가지와 관련 문서를 업로드하는 것만으로 귀사 AI 시스템의 적법성을 평가해 드립니다.
                </p>
                <div className="flex justify-center items-center space-x-3 text-blue-100 relative z-10">
                    <CheckCircle className="h-6 w-6 text-green-300" />
                    <span className="font-medium text-lg">최신 EU AI Act 기준 적용 완료</span>
                </div>
            </section>
        </div>
    );
}

export default Home;
