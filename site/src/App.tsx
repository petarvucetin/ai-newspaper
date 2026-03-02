import { BrowserRouter, Routes, Route } from "react-router-dom"
import { NewspaperPage } from "@/pages/NewspaperPage"
import { AdminPage } from "@/pages/AdminPage"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<NewspaperPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  )
}
