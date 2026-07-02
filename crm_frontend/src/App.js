import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Home from "./pages/Home";
import AdminLogin from "./pages/AdminLogin";
import ManagerLogin from "./pages/ManagerLogin";
import EmployeeLogin from "./pages/EmployeeLogin";
import SalesLogin from "./pages/SalesLogin";
import AccountantLogin from "./pages/AccountantLogin";

import AdminDashboard from "./pages/AdminDashboard";
import ManagerDashboard from "./pages/ManagerDashboard";
import EmployeeDashboard from "./pages/EmployeeDashboard";
import SalesDashboard from "./pages/SalesDashboard";
import AccountantDashboard from "./pages/AccountantDashboard";
import UserLogin from "./pages/UserLogin";
import UserSignup from "./pages/UserSignup";
import UserDashboard from "./pages/UserDashboard";
import Profile from "./pages/Profile";
import AdminUsers from "./pages/AdminUsers";
import AdminActivityLogs from "./pages/AdminActivityLogs";
import AdminCompany from "./pages/AdminCompany";
import NumberingConfig from "./pages/NumberingConfig";
import Contacts from "./pages/Contacts";
import ContactForm from "./pages/ContactForm";
import ContactDetail from "./pages/ContactDetail";
import Products from "./pages/Products";
import ProductForm from "./pages/ProductForm";
import ProductDetail from "./pages/ProductDetail";
import Leads from "./pages/Leads";
import LeadForm from "./pages/LeadForm";
import LeadDetail from "./pages/LeadDetail";
import Pipeline from "./pages/Pipeline";
import Deals from "./pages/Deals";
import DealForm from "./pages/DealForm";
import DealDetail from "./pages/DealDetail";
import Quotations from "./pages/Quotations";
import QuotationForm from "./pages/QuotationForm";
import QuotationDetail from "./pages/QuotationDetail";
import QuotationPreview from "./pages/QuotationPreview";
import QuotationApprovalQueue from "./pages/QuotationApprovalQueue";
import ClientQuoteView from "./pages/ClientQuoteView";
import SalesOrders from "./pages/SalesOrders";
import SalesOrderForm from "./pages/SalesOrderForm";
import SalesOrderDetail from "./pages/SalesOrderDetail";
import ClientOrderView from "./pages/ClientOrderView";
import Invoices from "./pages/Invoices";
import InvoiceForm from "./pages/InvoiceForm";
import InvoiceDetail from "./pages/InvoiceDetail";
import InvoicePreview from "./pages/InvoicePreview";
import InvoiceReviewQueue from "./pages/InvoiceReviewQueue";
import ClientInvoiceView from "./pages/ClientInvoiceView";
import ClientNotes from "./pages/ClientNotes";
import ClientNotesFollowUpQueue from "./pages/ClientNotesFollowUpQueue";
import SalesReports from "./pages/SalesReports";
import TaxReports from "./pages/TaxReports";
import PLReports from "./pages/PLReports";
import Projects from "./pages/Projects";
import ProjectForm from "./pages/ProjectForm";
import ProjectDetail from "./pages/ProjectDetail";
import ProjectMyTasks from "./pages/ProjectMyTasks";
import Leaves from "./pages/Leaves";
import Timesheets from "./pages/Timesheets";
import TimesheetForm from "./pages/TimesheetForm";
import TimesheetDetail from "./pages/TimesheetDetail";
import TimesheetApprovalQueue from "./pages/TimesheetApprovalQueue";
import Employees from "./pages/Employees";
import EmployeeDetail from "./pages/EmployeeDetail";
import Attendance from "./pages/Attendance";
import Recruitment from "./pages/Recruitment";
import RecruitmentJobDetail from "./pages/RecruitmentJobDetail";
import Payroll from "./pages/Payroll";
import PayslipDetail from "./pages/PayslipDetail";
import ApprovalsHub from "./pages/ApprovalsHub";
import InternalChat from "./pages/InternalChat";
import LeaveForm from "./pages/LeaveForm";
import LeaveDetail from "./pages/LeaveDetail";
import LeaveApprovalQueue from "./pages/LeaveApprovalQueue";
import TeamLeave from "./pages/TeamLeave";
import CustomerLedger from "./pages/CustomerLedger";
import CustomerLedgerStatement from "./pages/CustomerLedgerStatement";
import CustomerLedgerUnassigned from "./pages/CustomerLedgerUnassigned";
import VendorLedger from "./pages/VendorLedger";
import VendorLedgerStatement from "./pages/VendorLedgerStatement";
import VendorLedgerUnassigned from "./pages/VendorLedgerUnassigned";
import Expenses from "./pages/Expenses";
import ExpenseForm from "./pages/ExpenseForm";
import ExpenseDetail from "./pages/ExpenseDetail";
import ExpenseApprovalQueue from "./pages/ExpenseApprovalQueue";
import VendorBills from "./pages/VendorBills";
import VendorBillForm from "./pages/VendorBillForm";
import VendorBillDetail from "./pages/VendorBillDetail";
import VendorBillApprovalQueue from "./pages/VendorBillApprovalQueue";
import VendorBillPayablesSummary from "./pages/VendorBillPayablesSummary";
import PurchaseOrders from "./pages/PurchaseOrders";
import PurchaseOrderForm from "./pages/PurchaseOrderForm";
import PurchaseOrderDetail from "./pages/PurchaseOrderDetail";
import PurchaseOrderApprovalQueue from "./pages/PurchaseOrderApprovalQueue";
import Inventory from "./pages/Inventory";
import InventoryProductDetail from "./pages/InventoryProductDetail";
import InventoryRecordMovement from "./pages/InventoryRecordMovement";
import InventoryOpeningStock from "./pages/InventoryOpeningStock";
import InventoryMovements from "./pages/InventoryMovements";
import InventoryLowStock from "./pages/InventoryLowStock";
import StockMovements from "./pages/StockMovements";
import { StockMovementRecordIn, StockMovementRecordOut } from "./pages/StockMovementForm";
import StockMovementDetail from "./pages/StockMovementDetail";
import StockMovementSummary from "./pages/StockMovementSummary";
import Warehouses from "./pages/Warehouses";
import WarehouseLocationDetail from "./pages/WarehouseLocationDetail";
import WarehouseStockByLocation from "./pages/WarehouseStockByLocation";
import WarehouseRecordMovement from "./pages/WarehouseRecordMovement";
import WarehouseTransfer from "./pages/WarehouseTransfer";
import WarehouseTransferHistory from "./pages/WarehouseTransferHistory";
import FollowUps from "./pages/FollowUps";
import Payments from "./pages/Payments";
import ProtectedRoute from "./components/ProtectedRoute";

// New password‑reset pages
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import SystemConfiguration from "./pages/SystemConfiguration";
import EmailTemplates from "./pages/EmailTemplates";
import Documents from "./pages/Documents";
import WebsiteDashboard from "./pages/WebsiteDashboard";
import WebsitePages from "./pages/WebsitePages";
import WebsitePageEditor from "./pages/WebsitePageEditor";
import WebsiteForms from "./pages/WebsiteForms";
import WebsiteFormEditor from "./pages/WebsiteFormEditor";
import WebsiteBlog from "./pages/WebsiteBlog";
import WebsiteBlogEditor from "./pages/WebsiteBlogEditor";
import WebsiteSettings from "./pages/WebsiteSettings";
import PublicSite from "./pages/PublicSite";
import PublicBlog from "./pages/PublicBlog";
import ShopCatalog from "./pages/ShopCatalog";
import ShopProduct from "./pages/ShopProduct";
import ShopCart from "./pages/ShopCart";
import ShopCheckout from "./pages/ShopCheckout";
import ShopConfirmation from "./pages/ShopConfirmation";
import ShopAccount from "./pages/ShopAccount";
import ShopAccountLogin from "./pages/ShopAccountLogin";
import ShopAccountRegister from "./pages/ShopAccountRegister";
import ShopAccountOrderDetail from "./pages/ShopAccountOrderDetail";
import EcommerceDashboard from "./pages/EcommerceDashboard";
import EcommerceOrders from "./pages/EcommerceOrders";
import EcommerceOrderDetail from "./pages/EcommerceOrderDetail";
import EcommerceReturns from "./pages/EcommerceReturns";
import EcommerceCatalog from "./pages/EcommerceCatalog";
import EcommerceSettings from "./pages/EcommerceSettings";
import PosDashboard from "./pages/PosDashboard";
import PosTerminal from "./pages/PosTerminal";
import PosBills from "./pages/PosBills";
import PosBillDetail from "./pages/PosBillDetail";
import PosSessions from "./pages/PosSessions";
import PosReturns from "./pages/PosReturns";
import PosCatalog from "./pages/PosCatalog";
import PosSettings from "./pages/PosSettings";
import ManufacturingDashboard from "./pages/ManufacturingDashboard";
import WorkOrders from "./pages/WorkOrders";
import WorkOrderDetail from "./pages/WorkOrderDetail";
import WorkOrderForm from "./pages/WorkOrderForm";
import BomList from "./pages/BomList";
import BomEditor from "./pages/BomEditor";
import ManufacturingSettings from "./pages/ManufacturingSettings";
import QualityDashboard from "./pages/QualityDashboard";
import QualityInspections from "./pages/QualityInspections";
import QualityInspectionDetail from "./pages/QualityInspectionDetail";
import QualityInspectionForm from "./pages/QualityInspectionForm";
import QualityTemplates from "./pages/QualityTemplates";
import CorrectiveActions, { CorrectiveActionDetail, CorrectiveActionForm } from "./pages/CorrectiveActions";
import QualitySettings from "./pages/QualitySettings";
import QualityInspectionPoints from "./pages/QualityInspectionPoints";
import MaintenanceDashboard from "./pages/MaintenanceDashboard";
import MaintenanceAssets from "./pages/MaintenanceAssets";
import MaintenanceAssetDetail from "./pages/MaintenanceAssetDetail";
import MaintenanceAssetForm from "./pages/MaintenanceAssetForm";
import MaintenanceWorkOrders from "./pages/MaintenanceWorkOrders";
import MaintenanceWorkOrderDetail from "./pages/MaintenanceWorkOrderDetail";
import MaintenanceWorkOrderForm from "./pages/MaintenanceWorkOrderForm";
import MaintenancePmSchedule from "./pages/MaintenancePmSchedule";
import MaintenanceSettings from "./pages/MaintenanceSettings";
import FieldServiceDashboard from "./pages/FieldServiceDashboard";
import FieldServiceOrders from "./pages/FieldServiceOrders";
import FieldServiceOrderDetail from "./pages/FieldServiceOrderDetail";
import FieldServiceOrderForm from "./pages/FieldServiceOrderForm";
import FieldServiceSchedule from "./pages/FieldServiceSchedule";
import FieldServiceSettings from "./pages/FieldServiceSettings";
import SubscriptionsDashboard from "./pages/SubscriptionsDashboard";
import SubscriptionList from "./pages/SubscriptionList";
import SubscriptionPlans from "./pages/SubscriptionPlans";
import SubscriptionForm from "./pages/SubscriptionForm";
import SubscriptionDetail from "./pages/SubscriptionDetail";
import SubscriptionSettings from "./pages/SubscriptionSettings";
import RentalDashboard from "./pages/RentalDashboard";
import AiReportsHub from "./pages/AiReportsHub";
import AiInsightRunDetail from "./pages/AiInsightRunDetail";
import AiReportsSettings from "./pages/AiReportsSettings";
import WorkflowsHub from "./pages/WorkflowsHub";
import MarketingHub from "./pages/MarketingHub";
import MarketingCampaignDetail from "./pages/MarketingCampaignDetail";
import MarketingSettings from "./pages/MarketingSettings";
import AiAssistantHub from "./pages/AiAssistantHub";
import AiAssistantSettings from "./pages/AiAssistantSettings";
import MarketplaceHub from "./pages/MarketplaceHub";
import MarketplaceSettings from "./pages/MarketplaceSettings";
import WorkflowForm from "./pages/WorkflowForm";
import WorkflowDetail from "./pages/WorkflowDetail";
import WorkflowRuns from "./pages/WorkflowRuns";
import WorkflowRunDetail from "./pages/WorkflowRunDetail";
import WorkflowSettings from "./pages/WorkflowSettings";
import RentalCalendar from "./pages/RentalCalendar";
import RentalAssets from "./pages/RentalAssets";
import RentalContracts from "./pages/RentalContracts";
import RentalContractForm from "./pages/RentalContractForm";
import RentalContractDetail from "./pages/RentalContractDetail";
import RentalSettings from "./pages/RentalSettings";
import AdminBranding from "./pages/AdminBranding";
import RolesMatrix from "./pages/RolesMatrix";
import SendNotification from "./pages/SendNotification";


const ALL_ROLES = ["Admin", "Manager", "Employee", "Sales", "Accountant", "User"];
const STAFF_ROLES = ["Admin", "Manager", "Employee", "Sales", "Accountant"];

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />

        <Route path="/admin-login" element={<AdminLogin />} />
        <Route path="/manager-login" element={<ManagerLogin />} />
        <Route path="/employee-login" element={<EmployeeLogin />} />
        <Route path="/sales-login" element={<SalesLogin />} />
        <Route path="/accountant-login" element={<AccountantLogin />} />
        <Route path="/user-login" element={<UserLogin />} />
        <Route path="/user-signup" element={<UserSignup />} />
        <Route path="/quote/:token" element={<ClientQuoteView />} />
        <Route path="/order/:token" element={<ClientOrderView />} />
        <Route path="/invoice/:token" element={<ClientInvoiceView />} />
        <Route path="/s/:companySlug/blog/:postSlug" element={<PublicBlog />} />
        <Route path="/s/:companySlug/blog" element={<PublicBlog />} />
        <Route path="/s/:companySlug/shop/:productSlug" element={<ShopProduct />} />
        <Route path="/s/:companySlug/shop" element={<ShopCatalog />} />
        <Route path="/s/:companySlug/cart" element={<ShopCart />} />
        <Route path="/s/:companySlug/checkout/confirmation/:orderNumber" element={<ShopConfirmation />} />
        <Route path="/s/:companySlug/checkout" element={<ShopCheckout />} />
        <Route path="/s/:companySlug/account/login" element={<ShopAccountLogin />} />
        <Route path="/s/:companySlug/account/register" element={<ShopAccountRegister />} />
        <Route path="/s/:companySlug/account/orders/:orderNumber" element={<ShopAccountOrderDetail />} />
        <Route path="/s/:companySlug/account" element={<ShopAccount />} />
        <Route path="/s/:companySlug/:pageSlug" element={<PublicSite />} />
        <Route path="/s/:companySlug" element={<PublicSite />} />

        <Route
          path="/admin-dashboard"
          element={
            <ProtectedRoute allowedRoles={["Admin"]}>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manager-dashboard"
          element={
            <ProtectedRoute allowedRoles={["Manager"]}>
              <ManagerDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employee-dashboard"
          element={
            <ProtectedRoute allowedRoles={["Employee"]}>
              <EmployeeDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sales-dashboard"
          element={
            <ProtectedRoute allowedRoles={["Sales"]}>
              <SalesDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/accountant-dashboard"
          element={
            <ProtectedRoute allowedRoles={["Accountant"]}>
              <AccountantDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/user-dashboard"
          element={
            <ProtectedRoute allowedRoles={["User"]}>
              <UserDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute allowedRoles={ALL_ROLES}>
              <Profile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute
              allowedRoles={["Admin"]}
              requiredPermission="users.view"
            >
              <AdminUsers />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/activity-logs"
          element={
            <ProtectedRoute
              allowedRoles={["Admin"]}
              requiredPermission="activity.view"
            >
              <AdminActivityLogs />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/company"
          element={
            <ProtectedRoute
              allowedRoles={["Admin"]}
              requiredPermission="company.view"
            >
              <AdminCompany />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/branding"
          element={
            <ProtectedRoute allowedRoles={["Admin"]} requiredPermission="settings.edit">
              <AdminBranding />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/roles-matrix"
          element={
            <ProtectedRoute allowedRoles={["Admin"]} requiredPermission="roles.view">
              <RolesMatrix />
            </ProtectedRoute>
          }
        />
        <Route
          path="/send-notification"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="notifications.send">
              <SendNotification />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/send-notification"
          element={<Navigate to="/send-notification" replace />}
        />
        <Route
          path="/admin/numbering-config"
          element={
            <ProtectedRoute
              allowedRoles={["Admin"]}
              requiredPermission="numbering_config.view"
            >
              <NumberingConfig />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/system-config"
          element={
            <ProtectedRoute allowedRoles={["Admin"]}>
              <SystemConfiguration />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/email-templates"
          element={
            <ProtectedRoute allowedRoles={["Admin"]}>
              <EmailTemplates />
            </ProtectedRoute>
          }
        />
        <Route
          path="/contacts"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="contacts.view"
            >
              <Contacts />
            </ProtectedRoute>
          }
        />
        <Route
          path="/contacts/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="contacts.create"
            >
              <ContactForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/contacts/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="contacts.edit"
            >
              <ContactForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/contacts/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="contacts.view"
            >
              <ContactDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/products"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="products.view"
            >
              <Products />
            </ProtectedRoute>
          }
        />
        <Route
          path="/products/new"
          element={
            <ProtectedRoute
              allowedRoles={["Admin"]}
              requiredPermission="products.create"
            >
              <ProductForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/products/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={["Admin"]}
              requiredPermission="products.edit"
            >
              <ProductForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/products/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="products.view"
            >
              <ProductDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leads"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="leads.view"
            >
              <Leads />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leads/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="leads.create"
            >
              <LeadForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leads/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="leads.edit"
            >
              <LeadForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leads/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="leads.view"
            >
              <LeadDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pipeline"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="deals.view"
            >
              <Pipeline />
            </ProtectedRoute>
          }
        />
        <Route
          path="/deals"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="deals.view"
            >
              <Deals />
            </ProtectedRoute>
          }
        />
        <Route
          path="/deals/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="deals.create"
            >
              <DealForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/deals/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="deals.edit"
            >
              <DealForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/deals/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="deals.view"
            >
              <DealDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quotations"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="quotations.view"
            >
              <Quotations />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quotations/approval-queue"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="quotations.approve"
            >
              <QuotationApprovalQueue />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quotations/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="quotations.create"
            >
              <QuotationForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quotations/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="quotations.edit_draft"
            >
              <QuotationForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quotations/:id/preview"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="quotations.view"
            >
              <QuotationPreview />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quotations/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="quotations.view"
            >
              <QuotationDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sales-orders"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="sales_orders.view"
            >
              <SalesOrders />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sales-orders/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="sales_orders.create"
            >
              <SalesOrderForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sales-orders/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="sales_orders.edit_draft"
            >
              <SalesOrderForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sales-orders/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="sales_orders.view"
            >
              <SalesOrderDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/invoices"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="invoices.view"
            >
              <Invoices />
            </ProtectedRoute>
          }
        />
        <Route
          path="/invoices/review-queue"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="invoices.review"
            >
              <InvoiceReviewQueue />
            </ProtectedRoute>
          }
        />
        <Route
          path="/invoices/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="invoices.create"
            >
              <InvoiceForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/invoices/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="invoices.edit_draft"
            >
              <InvoiceForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/invoices/:id/preview"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="invoices.view"
            >
              <InvoicePreview />
            </ProtectedRoute>
          }
        />
        <Route
          path="/invoices/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="invoices.view"
            >
              <InvoiceDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/client-notes"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="client_notes.view"
            >
              <ClientNotes />
            </ProtectedRoute>
          }
        />
        <Route
          path="/client-notes/follow-ups"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="client_notes.manage_followups"
            >
              <ClientNotesFollowUpQueue />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tax-reports"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["tax_reports.view", "reports.view_financial"]}
            >
              <TaxReports />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pl-reports"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["pl_reports.view", "reports.view_financial"]}
            >
              <PLReports />
            </ProtectedRoute>
          }
        />
        <Route
          path="/customer-ledger/unassigned"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["customer_ledger.view", "invoices.view", "payments.view"]}
            >
              <CustomerLedgerUnassigned />
            </ProtectedRoute>
          }
        />
        <Route
          path="/customer-ledger/:contactId"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["customer_ledger.view", "invoices.view", "payments.view"]}
            >
              <CustomerLedgerStatement />
            </ProtectedRoute>
          }
        />
        <Route
          path="/customer-ledger"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["customer_ledger.view", "invoices.view", "payments.view"]}
            >
              <CustomerLedger />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-ledger/unassigned"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["vendor_ledger.view", "vendor_bills.view"]}
            >
              <VendorLedgerUnassigned />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-ledger/:contactId"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["vendor_ledger.view", "vendor_bills.view"]}
            >
              <VendorLedgerStatement />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-ledger"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["vendor_ledger.view", "vendor_bills.view"]}
            >
              <VendorLedger />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sales-reports"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="reports.view"
            >
              <SalesReports />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/my-tasks"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="projects.view"
            >
              <ProjectMyTasks />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="projects.create"
            >
              <ProjectForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="projects.edit"
            >
              <ProjectForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="projects.view"
            >
              <ProjectDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="projects.view"
            >
              <Projects />
            </ProtectedRoute>
          }
        />
        <Route
          path="/timesheets/approval-queue"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="timesheets.approve">
              <TimesheetApprovalQueue />
            </ProtectedRoute>
          }
        />
        <Route
          path="/timesheets/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="timesheets.create">
              <TimesheetForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/timesheets/:id/edit"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="timesheets.edit_own">
              <TimesheetForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/timesheets/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="timesheets.view">
              <TimesheetDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/timesheets"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="timesheets.view">
              <Timesheets />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employees/:userId"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="employees.view">
              <EmployeeDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employees"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="employees.view">
              <Employees />
            </ProtectedRoute>
          }
        />
        <Route
          path="/attendance"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="attendance.view">
              <Attendance />
            </ProtectedRoute>
          }
        />
        <Route
          path="/recruitment/jobs/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="recruitment.view">
              <RecruitmentJobDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/recruitment"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="recruitment.view">
              <Recruitment />
            </ProtectedRoute>
          }
        />
        <Route
          path="/payroll/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="payroll.view">
              <PayslipDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/payroll"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="payroll.view">
              <Payroll />
            </ProtectedRoute>
          }
        />
        <Route
          path="/approvals"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="approvals.view">
              <ApprovalsHub />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="chat.view">
              <InternalChat />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leaves/approval-queue"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="leaves.approve">
              <LeaveApprovalQueue />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leaves/team"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="leaves.view_all">
              <TeamLeave />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leaves/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="leaves.create">
              <LeaveForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leaves/:id/edit"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="leaves.edit_own">
              <LeaveForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leaves/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="leaves.view">
              <LeaveDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/leaves"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="leaves.view">
              <Leaves />
            </ProtectedRoute>
          }
        />
        <Route
          path="/expenses"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="expenses.view"
            >
              <Expenses />
            </ProtectedRoute>
          }
        />
        <Route
          path="/expenses/approval-queue"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="expenses.approve"
            >
              <ExpenseApprovalQueue />
            </ProtectedRoute>
          }
        />
        <Route
          path="/expenses/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="expenses.create"
            >
              <ExpenseForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/expenses/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="expenses.edit_own"
            >
              <ExpenseForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/expenses/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="expenses.view"
            >
              <ExpenseDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-bills"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="vendor_bills.view"
            >
              <VendorBills />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-bills/payables-summary"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="vendor_bills.view"
            >
              <VendorBillPayablesSummary />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-bills/approval-queue"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="vendor_bills.approve"
            >
              <VendorBillApprovalQueue />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-bills/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="vendor_bills.create"
            >
              <VendorBillForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-bills/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="vendor_bills.edit_own"
            >
              <VendorBillForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vendor-bills/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="vendor_bills.view"
            >
              <VendorBillDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/purchase-orders"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="purchase_orders.view"
            >
              <PurchaseOrders />
            </ProtectedRoute>
          }
        />
        <Route
          path="/purchase-orders/approval-queue"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="purchase_orders.approve"
            >
              <PurchaseOrderApprovalQueue />
            </ProtectedRoute>
          }
        />
        <Route
          path="/purchase-orders/new"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="purchase_orders.create"
            >
              <PurchaseOrderForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/purchase-orders/:id/edit"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="purchase_orders.edit_own"
            >
              <PurchaseOrderForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/purchase-orders/:id"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="purchase_orders.view"
            >
              <PurchaseOrderDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/warehouses"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="warehouses.view">
              <Warehouses />
            </ProtectedRoute>
          }
        />
        <Route
          path="/warehouses/stock"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="warehouses.view_stock">
              <WarehouseStockByLocation />
            </ProtectedRoute>
          }
        />
        <Route
          path="/warehouses/record-movement"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="warehouses.record_receipt">
              <WarehouseRecordMovement />
            </ProtectedRoute>
          }
        />
        <Route
          path="/warehouses/transfer"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="warehouses.transfer">
              <WarehouseTransfer />
            </ProtectedRoute>
          }
        />
        <Route
          path="/warehouses/transfers"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="warehouses.view">
              <WarehouseTransferHistory />
            </ProtectedRoute>
          }
        />
        <Route
          path="/warehouses/locations/:locationId"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="warehouses.view">
              <WarehouseLocationDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/stock-movements"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="stock_movements.view">
              <StockMovements />
            </ProtectedRoute>
          }
        />
        <Route
          path="/stock-movements/summary"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="stock_movements.view">
              <StockMovementSummary />
            </ProtectedRoute>
          }
        />
        <Route
          path="/stock-movements/in"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="stock_movements.record_in">
              <StockMovementRecordIn />
            </ProtectedRoute>
          }
        />
        <Route
          path="/stock-movements/out"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="stock_movements.record_out">
              <StockMovementRecordOut />
            </ProtectedRoute>
          }
        />
        <Route
          path="/stock-movements/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="stock_movements.view">
              <StockMovementDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inventory"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="inventory.view">
              <Inventory />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inventory/movements"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="inventory.view">
              <InventoryMovements />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inventory/low-stock"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="inventory.view">
              <InventoryLowStock />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inventory/record-movement"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="inventory.record_purchase">
              <InventoryRecordMovement />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inventory/opening-stock"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="inventory.record_opening">
              <InventoryOpeningStock />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inventory/:productId"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="inventory.view">
              <InventoryProductDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/follow-ups"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="reminders.view"
            >
              <FollowUps />
            </ProtectedRoute>
          }
        />
        <Route
          path="/payments"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermission="payments.view"
            >
              <Payments />
            </ProtectedRoute>
          }
        />
        <Route
          path="/documents"
          element={
            <ProtectedRoute
              allowedRoles={STAFF_ROLES}
              requiredPermissions={["files.view", "files.view_own"]}
            >
              <Documents />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.manage">
              <WebsiteSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/pages/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.manage">
              <WebsitePageEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/pages/:id/edit"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.manage">
              <WebsitePageEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/pages"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.view">
              <WebsitePages />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/forms/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.forms">
              <WebsiteFormEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/forms/:id/edit"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.forms">
              <WebsiteFormEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/forms"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.view">
              <WebsiteForms />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/blog/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.manage">
              <WebsiteBlogEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/blog/:id/edit"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.manage">
              <WebsiteBlogEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website/blog"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.view">
              <WebsiteBlog />
            </ProtectedRoute>
          }
        />
        <Route
          path="/website"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="website.view">
              <WebsiteDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ecommerce/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ecommerce.manage_settings">
              <EcommerceSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ecommerce/catalog"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ecommerce.manage_catalog">
              <EcommerceCatalog />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ecommerce/returns"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ecommerce.view">
              <EcommerceReturns />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ecommerce/orders/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ecommerce.view">
              <EcommerceOrderDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ecommerce/orders"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ecommerce.view">
              <EcommerceOrders />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ecommerce"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ecommerce.view">
              <EcommerceDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pos/terminal"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="pos.bill">
              <PosTerminal />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pos/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="pos.manage_settings">
              <PosSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pos/catalog"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="pos.manage_catalog">
              <PosCatalog />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pos/returns"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="pos.view">
              <PosReturns />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pos/sessions"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="pos.view">
              <PosSessions />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pos/bills/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="pos.view">
              <PosBillDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pos/bills"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="pos.view">
              <PosBills />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pos"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="pos.view">
              <PosDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="manufacturing.manage_settings">
              <ManufacturingSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing/quality"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.view">
              <QualityInspections />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing/boms/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="manufacturing.manage_bom">
              <BomEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing/boms/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="manufacturing.view">
              <BomEditor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing/boms"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="manufacturing.view">
              <BomList />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing/work-orders/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="manufacturing.create_wo">
              <WorkOrderForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing/work-orders/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="manufacturing.view">
              <WorkOrderDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing/work-orders"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="manufacturing.view">
              <WorkOrders />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manufacturing"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="manufacturing.view">
              <ManufacturingDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.manage_settings">
              <QualitySettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/inspection-points"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.manage_templates">
              <QualityInspectionPoints />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/templates"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.view">
              <QualityTemplates />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/corrective-actions/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.manage_capa">
              <CorrectiveActionForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/corrective-actions/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.view">
              <CorrectiveActionDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/corrective-actions"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.view">
              <CorrectiveActions />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/inspections/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.inspect">
              <QualityInspectionForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/inspections/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.view">
              <QualityInspectionDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality/inspections"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.view">
              <QualityInspections />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quality"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="quality.view">
              <QualityDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.manage_settings">
              <MaintenanceSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/pm-schedule"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.view">
              <MaintenancePmSchedule />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/work-orders/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.create_wo">
              <MaintenanceWorkOrderForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/work-orders/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.view">
              <MaintenanceWorkOrderDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/work-orders"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.view">
              <MaintenanceWorkOrders />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/assets/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.manage_assets">
              <MaintenanceAssetForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/assets/:id/edit"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.manage_assets">
              <MaintenanceAssetForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/assets/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.view">
              <MaintenanceAssetDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance/assets"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.view">
              <MaintenanceAssets />
            </ProtectedRoute>
          }
        />
        <Route
          path="/maintenance"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="maintenance.view">
              <MaintenanceDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/field-service/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="field_service.manage_settings">
              <FieldServiceSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/field-service/schedule"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="field_service.view">
              <FieldServiceSchedule />
            </ProtectedRoute>
          }
        />
        <Route
          path="/field-service/orders/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="field_service.create">
              <FieldServiceOrderForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/field-service/orders/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="field_service.view">
              <FieldServiceOrderDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/field-service/orders"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="field_service.view">
              <FieldServiceOrders />
            </ProtectedRoute>
          }
        />
        <Route
          path="/field-service"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="field_service.view">
              <FieldServiceDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/subscriptions/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="subscriptions.manage_settings">
              <SubscriptionSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/subscriptions/plans"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="subscriptions.view">
              <SubscriptionPlans />
            </ProtectedRoute>
          }
        />
        <Route
          path="/subscriptions/list"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="subscriptions.view">
              <SubscriptionList />
            </ProtectedRoute>
          }
        />
        <Route
          path="/subscriptions/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="subscriptions.create">
              <SubscriptionForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/subscriptions/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="subscriptions.view">
              <SubscriptionDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/subscriptions"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="subscriptions.view">
              <SubscriptionsDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rental/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="rental.manage_settings">
              <RentalSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rental/calendar"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="rental.view">
              <RentalCalendar />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rental/assets"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="rental.view">
              <RentalAssets />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rental/contracts/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="rental.create">
              <RentalContractForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rental/contracts/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="rental.view">
              <RentalContractDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rental/contracts"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="rental.view">
              <RentalContracts />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rental"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="rental.view">
              <RentalDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ai-reports/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ai_reports.manage_settings">
              <AiReportsSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ai-reports/runs/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ai_reports.view">
              <AiInsightRunDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ai-reports"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ai_reports.view">
              <AiReportsHub />
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="workflows.manage_settings">
              <WorkflowSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows/runs/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="workflows.view">
              <WorkflowRunDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows/runs"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="workflows.view">
              <WorkflowRuns />
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows/new"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="workflows.create">
              <WorkflowForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows/:id/edit"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="workflows.edit">
              <WorkflowForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="workflows.view">
              <WorkflowDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="workflows.view">
              <WorkflowsHub />
            </ProtectedRoute>
          }
        />
        <Route
          path="/marketing/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="marketing.manage_settings">
              <MarketingSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/marketing/campaigns/:id"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="marketing.view">
              <MarketingCampaignDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/marketing"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="marketing.view">
              <MarketingHub />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ai-assistant/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ai_assistant.manage_settings">
              <AiAssistantSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ai-assistant"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="ai_assistant.view">
              <AiAssistantHub />
            </ProtectedRoute>
          }
        />
        <Route
          path="/marketplace/settings"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="marketplace.manage_settings">
              <MarketplaceSettings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/marketplace"
          element={
            <ProtectedRoute allowedRoles={STAFF_ROLES} requiredPermission="marketplace.view">
              <MarketplaceHub />
            </ProtectedRoute>
          }
        />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
      </Routes>
    </BrowserRouter>
  );
}


export default App;
