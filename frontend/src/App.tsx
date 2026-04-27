import { BrowserRouter, Route, Routes } from "react-router-dom"
import SearchPage from "./pages/SearchPage"
import ResultsPage from "./pages/ResultsPage"
import OrdersPage from "./pages/OrdersPage"
import ProcurementBoard from "./pages/ProcurementBoard"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/procurement" element={<ProcurementBoard />} />
      </Routes>
    </BrowserRouter>
  )
}
