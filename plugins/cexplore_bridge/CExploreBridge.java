//Bridge to The Little Hat and CExplore
//@author octorock
//@category _NEW_
//@keybinding 
//@menupath Tools.CExplore Bridge
//@toolbar 

// Adapted from https://github.com/radareorg/ghidra-r2web
// Get previous DecompileOptions from https://github.com/NationalSecurityAgency/ghidra/issues/1520

import ghidra.app.script.GhidraScript;
import ghidra.program.model.util.*;
import ghidra.program.model.reloc.*;
import ghidra.program.model.data.*;
import ghidra.program.model.block.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.scalar.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.pcode.*;
import ghidra.program.model.address.*;
import ghidra.app.decompiler.*;
import com.sun.net.httpserver.*;
import java.io.*;
import java.net.*;
import ghidra.framework.plugintool.util.*;
import ghidra.app.cmd.function.*;
import ghidra.app.util.parser.*;

public class CExploreBridge extends GhidraScript {
	static HttpServer server = null;

	class Response {
		private int code;
		private String text;
		public Response(int code, String text) {
			this.code = code;
			this.text = text;
		}

		public int getCode() {
			return code;
		}
		public String getText() {
			return text;
		}
	}

	abstract class BaseHandler implements HttpHandler {
		private String path;

		public void setPath(String path) {
			this.path = path;
		}


		public abstract Response handle(String data) throws Exception;


		public void handle(HttpExchange t) throws IOException {
			String name = t.getRequestURI().getPath().toString().substring(path.length()+1);

			String response;
			int code = 200;
			try {
				Response r = handle(name);
				response = r.getText();
				code = r.getCode();
			} catch (Exception e) {
				code = 500;
				println(e.toString());
				response = e.toString();
			}
			try {
				byte[] bytes = response.getBytes();
				t.sendResponseHeaders(code, bytes.length);
				OutputStream os = t.getResponseBody();
				os.write(bytes);
				os.close();
			} catch (Exception e) {
				println(e.toString());
			}

		}

	}

	class ShutdownHandler implements HttpHandler {
		@Override
		public void handle(HttpExchange t) throws IOException {
			try {
				int code = 200;
				String response = "Stopping server in one second.";
				byte[] bytes = response.getBytes();
				t.sendResponseHeaders(code, bytes.length);
				OutputStream os = t.getResponseBody();
				os.write(bytes);
				os.close();
			} catch (Exception e) {
				println(e.toString());
			}
			new Thread(new Runnable(){
				public void run() {
					server.stop(1);
				};
			}).start();			
		}
	}

	class DecompileHandler implements HttpHandler {
		public void handle(HttpExchange t) throws IOException {
			String name = t.getRequestURI().getPath().toString().substring(11);
			String response;
			int code = 200;
			try {
				response = decompile(name);
			} catch (Exception e) {
				code = 500;
				println(e.toString());
				response = e.toString();
			}
			try {
				byte[] bytes = response.getBytes();
				t.sendResponseHeaders(code, bytes.length);
				OutputStream os = t.getResponseBody();
				os.write(bytes);
				os.close();
			} catch (Exception e) {
				println(e.toString());
			}

		}
	}

	class GoToHandler implements HttpHandler {
		public void handle(HttpExchange t) throws IOException {
			String name = t.getRequestURI().getPath().toString().substring(6);
			String response = "";
			int code = 200;
			try {
				goToFunction(name);
			} catch (Exception e) {
				code = 500;
				response = e.toString();
			}
			try {
				byte[] bytes = response.getBytes();
				t.sendResponseHeaders(code, bytes.length);
				OutputStream os = t.getResponseBody();
				os.write(bytes);
				os.close();
			} catch (Exception e) {
				println(e.toString());
			}

		}
	}

	public void goToFunction(String functionName) {
		Function f = getFunction(functionName);
		if (f == null) {
			throw new RuntimeException("Function " + functionName + " not found.");
		}
		goTo(f);

	}

	public String decompile(String functionName) {
		Function f = getFunction(functionName);
		if (f == null) {
			throw new RuntimeException("Function " + functionName + " not found.");
		}

		// Go to the function so that it can be edited in the next step
		goTo(f);
		DecompInterface di = new DecompInterface();
		// Apply options
		DecompileOptions options = new DecompileOptions();
		var tool = state.getTool();
		if (tool != null) {
			var service = tool.getService(OptionsService.class);
			if (service != null) {
				var opt = service.getOptions("Decompiler");
				options.grabFromToolAndProgram(null, opt, f.getProgram());
			}
		}

		di.setOptions(options);
		println("Simplification style: " + di.getSimplificationStyle());
		println("Debug enables: " + di.debugEnabled());

		println(String.format("Decompiling %s() at 0x%s", f.getName(), f.getEntryPoint().toString()));

		println("Program: " + di.openProgram(getCurrentProgram()));

		// Decompile with a 5-seconds timeout
		DecompileResults dr = di.decompileFunction(f, 5, null);
		println("Decompilation completed: " + dr.decompileCompleted());

		DecompiledFunction df = dr.getDecompiledFunction();
		println(df.getC());
		return df.getC();
	}

	public Address parseSymbolOrAddress(String text) {
		var symbol = getSymbol(text, null);
		if (symbol != null) {
			return symbol.getAddress();
		}
		return parseAddress(text);
	}

	public void applyTypeForGlobal(String address, String type) throws Exception {
		var dataTypes = getDataTypes(type);
		if (dataTypes.length > 1) {
			throw new RuntimeException(dataTypes.length + " data types for " + type);
			// TODO let user determine correct data type?
		}
		if (dataTypes.length == 0) {
			throw new RuntimeException("No data type " + type + " found.");
		}
		var dataType = dataTypes[0];
		var addr = parseSymbolOrAddress(address);

		start();
		DataUtilities.createData(getCurrentProgram(), addr, dataType, 0, false,
				DataUtilities.ClearDataMode.CLEAR_ALL_CONFLICT_DATA);
		end(true);
	}

	public void applyFunctionSignature(String address, String signatureStr) throws Exception {
		var addr = parseSymbolOrAddress(address);
		var func = getFunctionAt(addr);
		var signature = new FunctionSignatureParser(currentProgram.getDataTypeManager(), null)
				.parse(func.getSignature(), signatureStr);
		var cmd = new ApplyFunctionSignatureCmd(addr, signature, SourceType.IMPORTED, true, false);
		start();
		runCommand(cmd);
		end(true);
	}

	class FunctionTypeHandler extends BaseHandler {

		@Override
		public CExploreBridge.Response handle(String data) throws Exception {
			String[] arr = data.split("/");
			if (arr.length != 2) {
				throw new IllegalArgumentException("function_name/function_signature");
			}
			applyFunctionSignature(arr[0], arr[1]);
			return new Response(200, "Applied function signature");
		}
		
	}

	class GlobalTypeHandler extends BaseHandler {
		@Override
		public CExploreBridge.Response handle(String data) throws Exception {
			String[] arr = data.split("/");
			if (arr.length != 2) {
				throw new IllegalArgumentException("symbol_name/data_type");
			}
			applyTypeForGlobal(arr[0], arr[1]);
			return new Response(200, "Applied data type to global.");
		}
	}

	private void addHandler(String path, BaseHandler handler) {
		handler.setPath(path);
		server.createContext(path, handler);
	}

	public void run() throws Exception {
		if (server != null) {
			server.stop(0);
		}
		server = HttpServer.create(new InetSocketAddress(10242), 0);
		server.createContext("/shutdown", new ShutdownHandler());
		server.createContext("/decompile", new DecompileHandler());
		server.createContext("/goto", new GoToHandler());
		addHandler("/functionType", new FunctionTypeHandler());
		addHandler("/globalType", new GlobalTypeHandler());
		server.start();

		boolean res = askYesNo("CExplore Bridge is running",
				"Press yes to stop the server.\nPress 'no' to continue in background (EXPERIMENTAL)");
		if (res) {
			println("Stopping server.");
			server.stop(0);
		} else {
			println("Server continues running in the background...");
		}
	}

}
