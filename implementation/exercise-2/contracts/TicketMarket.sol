// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title TicketMarket
/// @notice On-chain event ticketing: creation, purchase, transfer, and resale.
contract TicketMarket {

    struct Event {
        uint id;
        string name;
        string date;
        string venue;
        uint totalSupply;
        uint available;
        uint priceWei;
        bool exists;
    }

    struct Ticket {
        uint id;
        uint eventId;
        address owner;
        bool forResale;
        uint resalePrice;
    }

    address public owner;
    uint private nextEventId;
    uint private nextTicketId;

    mapping(uint => Event) public events;
    mapping(uint => Ticket) public tickets;
    mapping(address => uint[]) public ticketsByOwner;
    uint[] public eventIds;
    uint[] public ticketIds;

    event TicketPurchased(address indexed buyer, uint ticketId, uint eventId, uint paid);
    event TicketTransferred(uint indexed ticketId, address from, address to);
    event TicketListed(uint indexed ticketId, uint resalePrice);
    event TicketDelisted(uint indexed ticketId);
    event TicketResold(uint indexed ticketId, address from, address to, uint paid);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        nextEventId = 1;
        nextTicketId = 1;
        _createEvent("Rock Night",   "2026-05-10", "The Venue",  100, 0.01 ether);
        _createEvent("Jazz Evening", "2026-05-17", "Blue Note",   50, 0.005 ether);
    }

    // ── Admin ──────────────────────────────────────────────────────────────

    function createEvent(
        string memory name,
        string memory date,
        string memory venue,
        uint totalSupply,
        uint priceWei
    ) external onlyOwner {
        require(bytes(name).length > 0, "Name required");
        require(totalSupply > 0, "Supply must be > 0");
        require(priceWei > 0, "Price must be > 0");
        _createEvent(name, date, venue, totalSupply, priceWei);
    }

    function releaseTickets(uint eventId, uint qty) external onlyOwner {
        require(events[eventId].exists, "Event does not exist");
        require(qty > 0, "Qty must be > 0");
        events[eventId].available += qty;
        events[eventId].totalSupply += qty;
    }

    // ── User ───────────────────────────────────────────────────────────────

    function buyTicket(uint eventId) external payable {
        require(events[eventId].exists, "Event does not exist");
        require(events[eventId].available > 0, "Sold out");
        require(msg.value >= events[eventId].priceWei, "Insufficient payment");

        events[eventId].available -= 1;
        uint ticketId = nextTicketId++;
        tickets[ticketId] = Ticket(ticketId, eventId, msg.sender, false, 0);
        ticketIds.push(ticketId);
        ticketsByOwner[msg.sender].push(ticketId);

        emit TicketPurchased(msg.sender, ticketId, eventId, msg.value);
    }

    function transferTicket(uint ticketId, address to) external {
        require(tickets[ticketId].owner == msg.sender, "Not ticket owner");
        require(!tickets[ticketId].forResale, "Delist before transfer");
        require(to != address(0), "Invalid address");

        _removeFromOwner(msg.sender, ticketId);
        tickets[ticketId].owner = to;
        ticketsByOwner[to].push(ticketId);

        emit TicketTransferred(ticketId, msg.sender, to);
    }

    function listForResale(uint ticketId, uint priceWei) external {
        require(tickets[ticketId].owner == msg.sender, "Not ticket owner");
        require(!tickets[ticketId].forResale, "Already listed");
        require(priceWei > 0, "Price must be > 0");

        tickets[ticketId].forResale = true;
        tickets[ticketId].resalePrice = priceWei;

        emit TicketListed(ticketId, priceWei);
    }

    function delistTicket(uint ticketId) external {
        require(tickets[ticketId].owner == msg.sender, "Not ticket owner");
        require(tickets[ticketId].forResale, "Not listed");

        tickets[ticketId].forResale = false;
        tickets[ticketId].resalePrice = 0;

        emit TicketDelisted(ticketId);
    }

    function buyResaleTicket(uint ticketId) external payable {
        Ticket storage t = tickets[ticketId];
        require(t.forResale, "Not for resale");
        require(msg.value >= t.resalePrice, "Insufficient payment");
        require(t.owner != msg.sender, "Cannot buy own ticket");

        address seller = t.owner;
        uint price = t.resalePrice;

        _removeFromOwner(seller, ticketId);
        t.owner = msg.sender;
        t.forResale = false;
        t.resalePrice = 0;
        ticketsByOwner[msg.sender].push(ticketId);

        (bool sent, ) = payable(seller).call{value: price}("");
        require(sent, "Payment to seller failed");

        emit TicketResold(ticketId, seller, msg.sender, msg.value);
    }

    // ── Views ──────────────────────────────────────────────────────────────

    function getEvents() external view returns (Event[] memory) {
        Event[] memory list = new Event[](eventIds.length);
        for (uint i = 0; i < eventIds.length; i++) {
            list[i] = events[eventIds[i]];
        }
        return list;
    }

    function getTicketsByOwner(address addr) external view returns (Ticket[] memory) {
        uint[] memory ids = ticketsByOwner[addr];
        Ticket[] memory list = new Ticket[](ids.length);
        for (uint i = 0; i < ids.length; i++) {
            list[i] = tickets[ids[i]];
        }
        return list;
    }

    function getResaleTickets() external view returns (Ticket[] memory) {
        uint count = 0;
        for (uint i = 0; i < ticketIds.length; i++) {
            if (tickets[ticketIds[i]].forResale) count++;
        }
        Ticket[] memory list = new Ticket[](count);
        uint idx = 0;
        for (uint i = 0; i < ticketIds.length; i++) {
            if (tickets[ticketIds[i]].forResale) {
                list[idx++] = tickets[ticketIds[i]];
            }
        }
        return list;
    }

    function withdraw() external onlyOwner {
        uint bal = address(this).balance;
        require(bal > 0, "Nothing to withdraw");
        (bool sent, ) = payable(owner).call{value: bal}("");
        require(sent, "Withdraw failed");
    }

    // ── Internal ───────────────────────────────────────────────────────────

    function _createEvent(
        string memory name,
        string memory date,
        string memory venue,
        uint totalSupply,
        uint priceWei
    ) internal {
        uint id = nextEventId++;
        events[id] = Event(id, name, date, venue, totalSupply, totalSupply, priceWei, true);
        eventIds.push(id);
    }

    function _removeFromOwner(address addr, uint ticketId) internal {
        uint[] storage arr = ticketsByOwner[addr];
        for (uint i = 0; i < arr.length; i++) {
            if (arr[i] == ticketId) {
                arr[i] = arr[arr.length - 1];
                arr.pop();
                break;
            }
        }
    }
}
