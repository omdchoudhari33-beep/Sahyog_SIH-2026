export default function StatCard({ value, label }) {
  return (
    <div className="gov-card px-5 py-4 text-center">
      <div className="font-serif text-3xl font-bold text-gov-blue-800">{value}</div>
      <div className="mt-1 text-sm text-gray-600">{label}</div>
    </div>
  );
}
