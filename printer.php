<?php
// Small Failsafe
if(htmlspecialchars($_SERVER['HTTP_AUTHENTICATION'], ENT_QUOTES, 'UTF-8') != '4uth0rizedPr1nterz#') {
	header("HTTP/1.1 401 Unauthorized");
    exit;
}
require_once('mysql.php');

//$payload = json_decode(file_get_contents('php://input'), true);
$payload = file_get_contents('php://input');
//echo(var_dump($GLOBALS));
//$payload = $_POST['payload'];

$stmt = $conn->prepare('INSERT INTO printers (payload, timestamp) VALUES (?, NOW())');
$stmt->bind_param('s', $payload);
$stmt->execute();

?>